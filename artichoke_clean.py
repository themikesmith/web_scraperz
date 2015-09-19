from urllib import quote_plus
from urlparse import urlsplit, urlunsplit, parse_qs
import re
import geocoder
from super_requests import get_html_from_url
from BeautifulSoup import BeautifulSoup, Comment
from HTMLParser import HTMLParser
from sys import stderr
import traceback
from super_dt_parser import safe_dt_parse
from posting_class import Posting


class PostingScraper:
    """
    Interface for scrapers for posting websites.
    Implements "get postings" from a 'base url' construct
    """

    _html_parser = HTMLParser()

    def __init__(self, base):
        """
        initialize the scraper with a base url
        """
        r = urlsplit(base)
        self.scheme = r.scheme
        self.source = r.netloc

    @staticmethod
    def _encode_unicode(s):
        return s.encode('utf8')

    @staticmethod
    def _remove_none_from_things(provided_list):
        return [x for x in provided_list if x is not None]

    def _clean_post_url(self, url):
        """
        Cleans the url:
        - makes the scheme values uniform
        - adds the base url to any local urls
        :param url: the url to clean
        :return: the cleaned url
        """
        split_url = list(urlsplit(url))
        split_url[0] = self.scheme
        if not split_url[1]:
            split_url[1] = self.source
        split_url = tuple(split_url)
        return urlunsplit(split_url)

    @staticmethod
    def _get_cleaned_soup_from_html(html):
        # html = html.encode("utf8")
        soup = BeautifulSoup(PostingScraper._html_parser.unescape(html))
        # soup = BeautifulSoup(html, "html.parser")
        # get rid of all HTML comments, as they show up in soup's .text results
        comments = soup.findAll(text=lambda x: isinstance(x, Comment))
        # comments = soup.find_all(text=lambda x: isinstance(x, Comment))
        [comment.extract() for comment in comments]
        return soup

    @staticmethod
    def _get_cleaned_soup_from_url(url, dynamic=False, id_to_wait_for=None):
        """
        Wrapper for getting html from url, parse as BeautifulSoup, extract comments
        :param url: the url to request
        :param dynamic: True if URL contains dynamic content, false otherwise
        :param id_to_wait_for: an ID of an object on the page to wait for loading, used if dynamic
        :return: the resulting BeautifulSoup object
        """
        try:
            text = get_html_from_url(url, dynamic=dynamic, id_to_wait_for=id_to_wait_for)
        except ValueError:  # TODO: how handle if site times out or refuses connection?
            traceback.print_exc(file=stderr)
            text = ""  # just set blank if we can't get it for now.
        return PostingScraper._get_cleaned_soup_from_html(text)

    def get_postings(self, query, pages=1):
        """
        Gather results, given a query and the number of pages of results desired.
        A posting is a dict with the following minimum attributes:
            - text description
            - source
            - unique id
            - title
            - date posted
            - url
        Postings from websites may contain more information, e.g., price or location
        :param query: query to use on the site
        :param pages: number of pages of results desired
        :return: a list of postings, each of which is a dict.
        """
        raise NotImplementedError("Should have implemented this")


class CraigslistScraper(PostingScraper):
    _post_title_attrs = {"class": "postingtitletext"}

    def __init__(self, base_url):
        # if base == 'baltimore':
        #     base = 'http://baltimore.craigslist.org'
        if base_url is None or not base_url:
            raise ValueError("A base url must be specified for a Craigslist Scraper.")
        PostingScraper.__init__(self, base_url)

    def _get_info_from_clp_posting(self, url):
        posting = Posting({'source': self.source})
        soup = PostingScraper._get_cleaned_soup_from_url(url)
        posting['url'] = url
        try:
            posting['title'] = PostingScraper._encode_unicode(soup.find(attrs=CraigslistScraper._post_title_attrs).text)
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        try:
            loc = soup.find(href=re.compile("google.com/maps"))['href']
            g = geocoder.google(loc[loc.find('@')+1:-1].split(',')[:-1], method='reverse')
            posting['state'] = g.state
            posting['city'] = g.city
            posting['country'] = g.country
        except:
            pass
        try:
            posting['price'] = PostingScraper._encode_unicode(soup.find(text=re.compile('.*compensation.*')).parent.findChild('b').text).replace('$', '')
        except:
            pass
        try:
            posting['description'] = PostingScraper._encode_unicode(soup.find('section', {'id': 'postingbody'}).text)
        except:
            pass
        try:
            posting['date_posted'] = soup.find('time')['datetime']
        except:
            pass
        try:
            posting['unique_id'] = 'clgig'+re.match('[^\d]*(\d+).html', url).group(1)
        except:
            pass
        return posting

    def get_postings(self, query, pages=1):
        try:
            query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
            posts = []  # temporary variable to store all of the posting data
            for i in range(1, pages + 1):
                search_url = urlunsplit((self.scheme, self.source, "/search/ggg",
                                         "query=%s&sort=date?s=%d" % (query, i*100), ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                try:
                    posts += [self._clean_post_url(a['href']) for a in soup.findAll('a', {'data-id': re.compile('\d+')})]
                except KeyError:  # handle if no href
                    pass
            return list(set(PostingScraper._remove_none_from_things(
                [self._get_info_from_clp_posting(post) for post in posts])))
        except Exception:
            traceback.print_exc(file=stderr)
            return []


class UpworkScraper(PostingScraper):

    _job_search_result_link_attrs = {"class": "break", "itemprop": "url"}
    _job_url_attrs = {"property": "og:url"}
    _job_container_attrs = {"class": "container", "itemtype": "http://schema.org/JobPosting"}
    _job_dateposted_attrs = {"itemprop": "datePosted"}
    _job_descrip_aircard_attrs = {"class": "air-card-group"}
    _job_skill_tag_attrs = {"class": re.compile("^o-tag-skill")}
    _div_row_attrs = {'class': 'row'}

    def __init__(self):
        PostingScraper.__init__(self, "http://www.upwork.com")

    def _get_info_from_upwork_posting(self, posting_soup):
        """
        Given an Upwork article HTML object, extract the desired information and return as a dict
        :param posting_soup: the Soup-ed HTML
        :return: the data in a dict
        """
        posting = Posting({'source': self.source})
        # url
        try:
            url = posting_soup.find('meta', attrs=UpworkScraper._job_url_attrs)
            if url is not None:
                posting['url'] = self._clean_post_url(url['content'])
                posting['title'] = PostingScraper._encode_unicode(url.text)
                url_parts = urlsplit(posting['url'])
                if url_parts.path:
                    sections = url_parts.path.rsplit('/')
                    [sections.remove(s) for s in sections if not s]
                    posting['unique_id'] = sections[-1]
        except (KeyError, AttributeError):
            # traceback.print_exc(file=stderr)
            pass
        container = posting_soup.find(attrs=UpworkScraper._job_container_attrs)
        # date posted
        date_posted_span = container.find(attrs=UpworkScraper._job_dateposted_attrs)
        try:  # it's in the 'popover' attribute
            posting['date_posted'] = safe_dt_parse(date_posted_span['popover'])
        except (KeyError, AttributeError, ValueError, TypeError):
            # traceback.print_exc(file=stderr)
            pass
        # price
        # second row of container, first element, first row inside that
        try:
            second_row = container.findAll('div', attrs=UpworkScraper._div_row_attrs)[1]
            try:
                first_child = second_row.find('div')
                price_row = first_child.find('div', attrs=UpworkScraper._div_row_attrs)
                try:
                    posting['price_info'] = PostingScraper._encode_unicode(price_row.text)
                except AttributeError:  # thrown if price_row is None
                    # traceback.print_exc(file=stderr)
                    pass
            except IndexError:  # thrown if second_row doesn't have a first_child
                # traceback.print_exc(file=stderr)
                pass
        except IndexError:  # thrown if container doesn't have a second 'row' tag
            # traceback.print_exc(file=stderr)
            pass
        # text
        try:
            description_air_card = container.find('div', attrs=UpworkScraper._job_descrip_aircard_attrs)
            posting['description'] = PostingScraper._encode_unicode(description_air_card.find('p').text)
        except AttributeError:  # handle if soup finds nothing
            # traceback.print_exc(file=stderr)
            pass
        # skills
        try:
            posting['skills'] = map(lambda x: PostingScraper._encode_unicode(x.text),
                                    container.findAll('a', attrs=UpworkScraper._job_skill_tag_attrs))
        except AttributeError:  # handle if soup finds nothing for skills
            pass
        # unique id
        return posting

    def get_postings(self, query, pages=1):
        try:
            query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
            posts = []
            # example url:
            # https://www.upwork.com/o/jobs/browse/?q=therapist
            for i in range(1, pages + 1):
                search_url = urlunsplit((self.scheme, self.source, "/o/jobs/browse/", "page=%d&q=%s" % (i, query), ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                # this url returns a list of postings of profiles. visit each profile
                for article in soup.findAll('article'):  # get all 'article'
                    url = article.find('a', attrs=UpworkScraper._job_search_result_link_attrs)
                    try:
                        posts.append(self._clean_post_url(url['href']))
                    except (TypeError, KeyError):
                        pass
            return list(set(PostingScraper._remove_none_from_things(
                map(self._get_info_from_upwork_posting,
                    map(PostingScraper._get_cleaned_soup_from_url, posts)))))
        except Exception:
            traceback.print_exc(file=stderr)
            return []


class GuruScraper(PostingScraper):

    _job_search_results_list_attr = {"class": "services", "id": "serviceList"}
    _job_search_result_list_item_attrs = {"class": re.compile(r"^serviceItem")}
    _job_search_results_header_attrs = {"class": "servTitle"}
    _job_url_meta_attrs = {"property": "og:url"}
    _job_date_posted_span_attrs = {"class": "dt-style1"}
    _job_duration_span_attrs = {"id": "spnDurationLeft"}
    _job_budget_div_attrs = {"class": "budget"}
    _job_skill_section_attrs = {"id": "skillsSec"}
    _job_skill_link_attrs = {"class": "skillItem"}
    _job_experience_reqs_section_attrs = {"itemprop": "experienceRequirements"}
    _job_title_attrs = {"itemprop": "title"}

    def __init__(self):
        PostingScraper.__init__(self, "http://www.guru.com")

    def _get_info_from_guru_job_page_soup(self, posting_soup):
        posting = Posting({'source': self.source})
        # url, and unique id
        url = posting_soup.find('meta', attrs=GuruScraper._job_url_meta_attrs)
        if url is not None:
            posting['url'] = self._clean_post_url(url['content'])
            url_parts = urlsplit(posting['url'])
            if url_parts.path:
                sections = url_parts.path.rsplit('/')
                [sections.remove(s) for s in sections if not s]
                posting['unique_id'] = sections[-1]
        # title
        try:
            title_header = posting_soup.find(attrs=GuruScraper._job_title_attrs)
            posting['title'] = PostingScraper._encode_unicode(title_header.text)
        except AttributeError:
            pass
        # date posted
        try:
            date_posted_span = posting_soup.find('span', attrs=GuruScraper._job_date_posted_span_attrs)
            posting['date_posted'] = safe_dt_parse(date_posted_span['data-date'])
        except (KeyError, AttributeError, ValueError):
            # traceback.print_exc(file=stderr)
            pass
        # duration
        try:
            duration_span = posting_soup.find('span', attrs=GuruScraper._job_duration_span_attrs)
            actual_date_span = duration_span.find('span')
            posting['duration'] = safe_dt_parse(actual_date_span['data-date'])
        except (KeyError, AttributeError, ValueError, TypeError):
            # traceback.print_exc(file=stderr)
            pass
        # budget
        try:
            budget_div = posting_soup.find('div', attrs=GuruScraper._job_budget_div_attrs)
            posting['budget'] = PostingScraper._encode_unicode(budget_div.text)
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        # skills
        try:
            skills_section = posting_soup.find(attrs=GuruScraper._job_skill_section_attrs)
            posting['skills'] = map(lambda x:
                                    PostingScraper._encode_unicode(PostingScraper._get_cleaned_soup_from_html(x).text),
                                    skills_section.find('a', attrs=GuruScraper._job_skill_link_attrs))
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        # experience, desription
        try:
            description_section = posting_soup.find(attrs=GuruScraper._job_experience_reqs_section_attrs)
            posting['description'] = PostingScraper._encode_unicode(
                PostingScraper._get_cleaned_soup_from_html(str(description_section)).text)
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        return posting

    def get_postings(self, query, pages=1):
        postings = []
        try:
            query = re.sub(' ', '-', query)  # funny syntax for guru website
            query = quote_plus(query)
            for page_num in range(1, pages + 1):
                search_url = urlunsplit((self.scheme, self.source, "d/jobs/q/%s/pg/%d" % (query, page_num), "", ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                services_list = soup.find(attrs=GuruScraper._job_search_results_list_attr)
                try:  # handle if there are more pages than results... services_list won't exist
                    for i, li in enumerate(services_list.findAll('li', attrs=GuruScraper._job_search_result_list_item_attrs)):
                        h2 = li.find('h2', attrs=GuruScraper._job_search_results_header_attrs)
                        a = h2.find('a')
                        postings.append(self._clean_post_url(a['href']))
                except (AttributeError, TypeError, KeyError):
                    # also handle misc errors, want to gracefully return postings we already have
                    # traceback.print_exc(file=stderr)
                    pass
            return list(set(PostingScraper._remove_none_from_things(
                map(self._get_info_from_guru_job_page_soup,
                    map(PostingScraper._get_cleaned_soup_from_url, postings)))))
        except Exception:
            traceback.print_exc(file=stderr)
            return []


class IndeedScraper(PostingScraper):
    _job_results_col_attrs = {"id": "resultsCol"}
    _job_row_result_div_attrs = {"class": re.compile(r"row.*result")}
    _job_location_span_attrs = {"class": "location"}
    _job_date_span_attrs = {"class": "date"}
    _job_description_span_attrs = {"itemprop": "description"}
    _job_summary_span_attrs = {"class": "summary"}

    def __init__(self, location=""):
        PostingScraper.__init__(self, "http://www.indeed.com")
        if location:
            self.location = location
        else:
            self.location = ""

    def _get_info_from_indeed_result(self, row_result_soup):
        posting = Posting({'source': self.source})
        # url, title
        try:
            url_data = row_result_soup.find('a')
            posting['url'] = self._clean_post_url(url_data['href'])
            posting['title'] = PostingScraper._encode_unicode(url_data.text)
        except (AttributeError, KeyError, TypeError):
            pass
        # id
        try:
            posting['unique_id'] = row_result_soup['data-jk']
        except KeyError:
            pass
        # location
        try:
            loc = row_result_soup.find('span', IndeedScraper._job_location_span_attrs).text
            if loc is not None:
                g = geocoder.google(loc, method='reverse')
                posting['location'] = (g.city, g.state, g.country)
        except (AttributeError, Exception):
            # traceback.print_exc(file=stderr)
            pass
        # date posted logic
        try:
            date_posted_span = row_result_soup.find('span', attrs=IndeedScraper._job_date_span_attrs)
            date_posted_text = PostingScraper._encode_unicode(date_posted_span.text).lower()
            if date_posted_text == "just posted":
                date_posted_text = 'now'
            try:
                posting['date_posted'] = safe_dt_parse(date_posted_text)  # also throws AttributeError
            except (AttributeError, ValueError):
                # traceback.print_exc(file=stderr)
                pass
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        # description
        try:
            posting['description'] = PostingScraper._encode_unicode(
                row_result_soup.find("span", attrs=IndeedScraper._job_description_span_attrs).text)
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        if 'description' not in posting:  # try summary instead
            try:
                posting['description'] = PostingScraper._encode_unicode(
                    row_result_soup.find('span', attrs=IndeedScraper._job_summary_span_attrs).text
                )
            except AttributeError:
                # traceback.print_exc(file=stderr)
                pass
        return posting

    def get_postings(self, query, pages=1):
        try:
            query = quote_plus(query)
            postings = []
            for page_num in range(1, pages+1):
                search_url = urlunsplit((self.scheme, self.source, "jobs",
                                         "q=%s&l=%s&sort=date&start=%d" % (query, self.location, (page_num-1)*10), ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                job_results_td = soup.find('td', attrs=IndeedScraper._job_results_col_attrs)
                try:
                    postings.extend(job_results_td.findAll('div', IndeedScraper._job_row_result_div_attrs))
                except AttributeError:
                    # traceback.print_exc(file=stderr)
                    pass
            return list(set(PostingScraper._remove_none_from_things(
                map(self._get_info_from_indeed_result, postings))))
        except Exception:
            traceback.print_exc(file=stderr)
            return []


class SimplyhiredScraper(PostingScraper):
    _job_results_list_div_attrs = {"class": "results"}
    _job_result_div_attrs = {"class": "job", "itemtype": re.compile(r"JobPosting")}
    _job_title_link_attrs = {"class": "title"}
    _job_tools_container_attrs = {"class": "tools_container"}
    _description_page_info_table_attrs = {"class": "info-table"}
    _description_page_description_attrs = {"class": "job-description"}
    _description_page_table_info_label_attrs = {"class": "info-label"}

    def __init__(self, location=""):
        PostingScraper.__init__(self, "http://www.simplyhired.com")
        if location:
            self.location = location
        else:
            self.location = ""

    def _get_info_from_simplyhired_result(self, result_soup):
        posting = Posting({'source': self.source})
        # external url, title
        try:
            title_link = result_soup.find('a', attrs=SimplyhiredScraper._job_title_link_attrs)
            posting['external_url'] = self._clean_post_url(title_link['href'])
            posting['title'] = PostingScraper._encode_unicode(title_link.text)
        except (AttributeError, KeyError, TypeError):
            # traceback.print_exc(file=stderr)
            pass
        # url
        description_page_url = None
        try:
            tools_container = result_soup.find('div', attrs=SimplyhiredScraper._job_tools_container_attrs)
            tools_links = tools_container.findAll('a')
            description_page_url = tools_links[-1]['href']
            posting['url'] = description_page_url
            posting['unique_id'] = description_page_url  # TODO i couldn't actually find a unique id?
        except (KeyError, AttributeError, IndexError):
            # traceback.print_exc(file=stderr)
            pass
        if description_page_url is not None:
            # follow posting url to long description, and date posted
            description_page_soup = PostingScraper._get_cleaned_soup_from_url(description_page_url)
            try:
                info_table = description_page_soup.find('table',
                                                        attrs=SimplyhiredScraper._description_page_info_table_attrs)
                # 4 rows: Company, Location, Date Posted, Source
                row_data_two = []
                trs = info_table.findAll('tr')
                for tr in trs:
                    tds = tr.findAll('td')
                    try:
                        last_td = tds[-1]
                        row_data_two.append(PostingScraper._encode_unicode(last_td.text))
                    except IndexError:
                        # traceback.print_exc(file=stderr)
                        pass
                info_labels = info_table.findAll('td', attrs=SimplyhiredScraper._description_page_table_info_label_attrs)
                info_labels = map(lambda x: PostingScraper._encode_unicode(x.text).lower(), info_labels)
                table_data = zip(info_labels, row_data_two)
                for label, value in table_data:
                    if not value.strip():
                        continue
                    if 'location' in label:
                        try:
                            g = geocoder.google(value, method='reverse')
                            posting['location'] = (g.city, g.state, g.country)
                        except Exception:
                            # traceback.print_exc(file=stderr)
                            pass
                    elif 'date posted' in label:
                        try:
                            posting['date_posted'] = safe_dt_parse(value)
                        except (AttributeError, ValueError):
                            # traceback.print_exc(file=stderr)
                            pass
                    elif 'source' in label:
                        posting['external_source'] = value
                    elif 'company' in label:
                        posting['company'] = value
            except AttributeError:
                # traceback.print_exc(file=stderr)
                pass
            # description
            try:
                description_div = description_page_soup.find('div', attrs=SimplyhiredScraper._description_page_description_attrs)
                posting['description'] = PostingScraper._encode_unicode(description_div.text)
            except AttributeError:
                # traceback.print_exc(file=stderr)
                pass
        return posting

    def get_postings(self, query, pages=1):
        try:
            postings = []
            query = quote_plus(query)
            for page_num in range(1, pages+1):
                # https://www.simplyhired.com/search?q=massage+therapist&l=baltimore%2C+md&pn=2
                search_url = urlunsplit((self.scheme, self.source, "search",
                                         "q=%s&l=%s&pn=%d" % (query, quote_plus(self.location.lower()), page_num), ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                job_results_list_div = soup.find('div', attrs=SimplyhiredScraper._job_results_list_div_attrs)
                try:
                    postings.extend(job_results_list_div.findAll('div', SimplyhiredScraper._job_result_div_attrs))
                except AttributeError:
                    # traceback.print_exc(file=stderr)
                    pass
            return list(set(PostingScraper._remove_none_from_things(
                map(self._get_info_from_simplyhired_result, postings))))
        except Exception:
            traceback.print_exc(file=stderr)
            return []


class ZipRecruiterScraper(PostingScraper):
    _job_list_div_attrs = {"id": "job_list"}
    _job_result_link_attrs = {"class": "job_link"}
    _job_posting_h1_title_attrs = {"itemprop": "title"}
    _job_posting_ogurl_attrs = {"property": "og:url"}
    _job_posting_p_date_posted_attrs = {"class": re.compile(r"^[Pp]osted.*")}
    _job_posting_div_description_attrs = {"itemprop": "description"}
    _job_posting_latlong_attrs = {"name": "geo.position"}
    _job_posting_locdiv_attrs = {"itemprop": "jobLocation"}

    def __init__(self, location=""):
        PostingScraper.__init__(self, "http://www.ziprecruiter.com")
        if location:
            self.location = location
        else:
            self.location = ""

    def get_postings(self, query, pages=1):
        try:
            postings = []
            query = quote_plus(query)
            for page_num in range(1, pages+1):
                # https://www.ziprecruiter.com/candidate/search?sort=best-match&search=writer&page=2&location=baltimore
                search_url = urlunsplit((self.scheme, self.source, "candidate/search",
                                         "sort=best-match&search=%s&location=%s&page=%d" %
                                         (query, quote_plus(self.location.lower()), page_num), ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                job_results_list_div = soup.find('div', attrs=ZipRecruiterScraper._job_list_div_attrs)
                try:
                    postings.extend(map(lambda x: x['href'],
                                        job_results_list_div.findAll('a', ZipRecruiterScraper._job_result_link_attrs)))
                except AttributeError:
                    # traceback.print_exc(file=stderr)
                    pass
            # note that we could return None if we go to an external url here
            postings = map(self._get_info_from_ziprecruiter_result, postings)
            return list(set(PostingScraper._remove_none_from_things(postings)))
        except Exception:
            traceback.print_exc(file=stderr)
            return []

    def _get_info_from_ziprecruiter_result(self, job_link):
        # print >> stderr, job_link
        soup = PostingScraper._get_cleaned_soup_from_url(job_link)
        if not len(soup):
            # print >> stderr, "returning none, soup false, link:%s" % job_link
            return None
        posting = Posting()
        # url
        try:
            url_meta = soup.find('meta', attrs=ZipRecruiterScraper._job_posting_ogurl_attrs)
            url = url_meta['content']
            posting.add_url(url)
            # id is the last series of alphanumeric characters after the last hyphen in the url path
            # e.g., /jobs/proedit-inc-18374379/contract-scientific-writer-2ccbf90f
            # would mean 2ccbf90f
            things = urlsplit(url)
            path = things[2]
            last_hyphen = path.rfind('-')
            if last_hyphen != -1:
                # print >> stderr, path[last_hyphen+1:]
                posting.add_id(path[last_hyphen+1:])
            else:
                # just take the whole url after the base
                # print >> stderr, "couldn't find id in url:%s" % url
                # print >> stderr, "making id:", path
                posting.add_id(path)
        except (TypeError, IndexError):
            # traceback.print_exc(file=stderr)
            pass
        # source
        posting.add_source(self.source)
        # title
        try:
            title_h1 = soup.find('h1', attrs=ZipRecruiterScraper._job_posting_h1_title_attrs)
            posting.add_title(PostingScraper._encode_unicode(title_h1.text))
        except AttributeError:  # if title_h1 is None
            # traceback.print_exc(file=stderr)
            pass
        # location
        try:
            # try to do the following first, more exact
            geoloc_meta = soup.find('meta', attrs=ZipRecruiterScraper._job_posting_latlong_attrs)['content']
            geoloc_meta = re.sub(";", ",", geoloc_meta)
            g = geocoder.google(geoloc_meta.split(','), method='reverse')
            # print >> stderr, "reverse by latlong, loc:%s => g:%s" % (geoloc_meta, str(g))
            posting['state'] = g.state
            posting['city'] = g.city
            posting['country'] = g.country
        except (TypeError, AttributeError, KeyError):
            # try to find the google map link
            try:
                maps_url = soup.find(href=re.compile(r"google\.com/maps|maps\.google\.com"))['href']
                things = urlsplit(maps_url)
                params = things[3]
                loc = parse_qs(params)
                loc_str = loc['q'][0]
                g = geocoder.google(loc_str)
                # print >> stderr, "normal by loc:%s => g:%s" % (loc_str, g)
                posting['state'] = g.state
                posting['city'] = g.city
                posting['country'] = g.country
            except (TypeError, AttributeError, KeyError, IndexError):
                # traceback.print_exc(file=stderr)
                pass
        # date posted
        try:
            try:  # try this first, but if we fail...
                date_posted_p = soup.find('p', attrs=ZipRecruiterScraper._job_posting_p_date_posted_attrs)
                # find first 'span'
                date_posted_span = date_posted_p.find('span')
                dt_text = re.sub(r"[Pp]osted", "", date_posted_span.text.lower()).strip()
                posting.add_date_posted(safe_dt_parse(dt_text))
            except AttributeError:
                try:
                    # ... double-check that we have a 'posted today / this week / 12 hours ago / whatever'
                    locdiv = soup.find('div', attrs=ZipRecruiterScraper._job_posting_locdiv_attrs)
                    header_div = locdiv.parent
                    date_p = header_div.findAll('p')[-1]
                    date_span = date_p.find('span')
                    date_span_text = date_span.text.lower()
                    if "posted" in date_span_text:
                        # and if so, take appropriate action
                        dt_text = re.sub(r"posted", "", date_span_text).strip()
                        posting.add_date_posted(safe_dt_parse(dt_text))
                    else:
                        # print >> stderr, "don't have a date found at url:%s" % job_link
                        pass
                except (AttributeError, IndexError):
                    # traceback.print_exc(file=stderr)
                    pass
        except ValueError as e:
            print >> stderr, "error parsing date posted string at url:%s" % job_link
            pass
        # description
        try:
            description_div = soup.find('div', attrs=ZipRecruiterScraper._job_posting_div_description_attrs)
            posting.add_description(PostingScraper._encode_unicode(description_div.text))
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        return posting


if __name__ == "__main__":
    scrapers = list()
    # scrapers.append(CraigslistScraper(base_url="http://baltimore.craigslist.org"))
    # scrapers.append(UpworkScraper())
    # scrapers.append(GuruScraper())
    # scrapers.append(IndeedScraper(location="baltimore"))
    # scrapers.append(SimplyhiredScraper(location="Baltimore, MD"))
    scrapers.append(ZipRecruiterScraper(location="baltimore"))
    keys_to_verify = ['source', 'unique_id', 'title', 'date_posted', 'description']
    for scraper in scrapers:
        print scraper.__class__
        for p in scraper.get_postings("computer thing", pages=50):
            for k, v in p.items():
                print k, " => ", v
            for k in keys_to_verify:
                if k not in p:
                    print '%s not there!!' % k
