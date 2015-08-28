from urllib import quote_plus
from urlparse import urlsplit, urlunsplit
import re
import geocoder
from super_requests import get_html_from_url
from BeautifulSoup import BeautifulSoup, Comment
from HTMLParser import HTMLParser
from sys import stderr
import traceback
from super_dt_parser import safe_dt_parse


class PostingScraper:
    """
    Interface for scrapers for posting websites.
    Implements "get postings" from a 'base url' construct
    """

    _html_parser = HTMLParser()

    def __init__(self, base):
        """
        initialize the scraper with a base url, and a source
        """
        r = urlsplit(base)
        self.scheme = r.scheme
        self.source = r.netloc

    @staticmethod
    def _encode_unicode(s):
        return s.encode('utf8')

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
            text = ""  # just set blank if we can't get it for now.
        return PostingScraper._get_cleaned_soup_from_html(text)

    def get_postings(self, query, pages=1):
        """
        Gather results, given a query and the number of pages of results desired.
        A posting is a dict with the following attributes:
            - url
            - price
            - location: state, city, country
            - text
            - unique id
            - date created
        Will be different for each website (duh)
        :param query: query to use on the site
        :param pages: number of pages of results desired
        :return: a list of postings, each of which is a dict.
        """
        raise NotImplementedError("Should have implemented this")


class CraigslistScraper(PostingScraper):
    def __init__(self, base):
        if base == 'baltimore':
            base = 'http://baltimore.craigslist.org'
        PostingScraper.__init__(self, base)

    def _get_info_from_clp_posting(self, url):
        posting = {}
        soup = PostingScraper._get_cleaned_soup_from_url(url)
        posting['url'] = url
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
            posting['text'] = PostingScraper._encode_unicode(soup.find('section', {'id': 'postingbody'}).text)
        except:
            pass
        try:
            posting['date_created'] = soup.find('time')['datetime']
        except:
            pass
        try:
            posting['unique_id'] = 'clgig'+re.match('[^\d]*(\d+).html', url).group(1)
        except:
            pass
        posting['source'] = self.source
        return posting

    def get_postings(self, query, pages=1):
        try:
            query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
            posts = []  # temporary variable to store all of the posting data
            for i in range(1, pages + 1):
                search_url = urlunsplit((self.scheme, self.source, "/search/ggg",
                                         "query=%s&sort=date?s=%d" % (query, pages*100), ""))
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                posts += [self._clean_post_url(a['href']) for a in soup.findAll('a', {'data-id': re.compile('\d+')})]
                # posts += [self._clean_post_url(a['href']) for a in soup.find_all('a', {'data-id': re.compile('\d+')})]
            return [self._get_info_from_clp_posting(post) for post in posts]
        except Exception:
            # traceback.print_exc(file=stderr)
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
        posting = {}
        # url
        url = posting_soup.find('meta', attrs=UpworkScraper._job_url_attrs)
        if url is not None:
            posting['url'] = self._clean_post_url(url['content'])
            url_parts = urlsplit(posting['url'])
            if url_parts.path:
                sections = url_parts.path.rsplit('/')
                [sections.remove(s) for s in sections if not s]
                posting['unique_id'] = sections[-1]
        container = posting_soup.find(attrs=UpworkScraper._job_container_attrs)
        # date posted
        date_posted_span = container.find(attrs=UpworkScraper._job_dateposted_attrs)
        try:  # it's in the 'popover' attribute
            posting['date_created'] = safe_dt_parse(date_posted_span['popover'])
        except (KeyError, AttributeError, ValueError):
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
        posting['source'] = self.source
        return posting

    def get_postings(self, query, pages=1):
        try:
            query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
            posts = []
            # example url:
            # https://www.upwork.com/o/jobs/browse/?q=therapist
            for i in range(1, pages + 1):
                search_url = urlunsplit((self.scheme, self.source, "/o/jobs/browse/", "page=%d&q=%s" % (i, query), ""))
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                # print soup
                # this url returns a list of postings of profiles. visit each profile
                for article in soup.findAll('article'):  # get all 'article'
                    url = article.find('a', attrs=UpworkScraper._job_search_result_link_attrs)
                    posts.append(self._clean_post_url(url['href']))
            return map(self._get_info_from_upwork_posting,
                       map(PostingScraper._get_cleaned_soup_from_url, posts))
        except Exception:
            # traceback.print_exc(file=stderr)
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

    def __init__(self):
        PostingScraper.__init__(self, "http://www.guru.com")

    def _get_info_from_guru_job_page_soup(self, posting_soup):
        posting = {}
        # url, and unique id
        url = posting_soup.find('meta', attrs=GuruScraper._job_url_meta_attrs)
        if url is not None:
            posting['url'] = self._clean_post_url(url['content'])
            url_parts = urlsplit(posting['url'])
            if url_parts.path:
                sections = url_parts.path.rsplit('/')
                [sections.remove(s) for s in sections if not s]
                posting['unique_id'] = sections[-1]
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
        except (KeyError, AttributeError, ValueError):
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
        posting['source'] = self.source
        return posting

    def get_postings(self, query, pages=1):
        postings = []
        try:
            query = re.sub(' ', '-', query)  # funny syntax for guru website
            query = quote_plus(query)
            search_url = urlunsplit((self.scheme, self.source, "d/jobs/q/%s/" % query, "", ""))
            soup = PostingScraper._get_cleaned_soup_from_url(search_url)
            services_list = soup.find(attrs=GuruScraper._job_search_results_list_attr)
            for i, li in enumerate(services_list.findAll('li', attrs=GuruScraper._job_search_result_list_item_attrs)):
                h2 = li.find('h2', attrs=GuruScraper._job_search_results_header_attrs)
                a = h2.find('a')
                postings.append(self._clean_post_url(a['href']))
            return map(self._get_info_from_guru_job_page_soup,
                       map(PostingScraper._get_cleaned_soup_from_url, postings))
        except Exception:
            # traceback.print_exc(file=stderr)
            return []


class ElanceScraper(PostingScraper):
    # api reference:
    # https://www.elance.com/q/api2/getting-started

    _job_search_results_div_attrs = {"id": "jobSearchResults"}
    _job_result_card_div_attrs = {"class": re.compile(r"^jobCard")}
    _job_card_url_attrs = {"class": "title"}

    def __init__(self):
        PostingScraper.__init__(self, "http://www.elance.com")

    def get_postings(self, query, pages=1):
        # https://www.elance.com/browse-jobs -- base
        # example query: https://www.elance.com/r/jobs/q-computer%20thing%20%21/
        # ex two: https://www.elance.com/r/jobs/q-computer
        # three: https://www.elance.com/r/jobs/q-computer%20thing
        postings = []
        query = quote_plus(query)
        try:
            search_url = urlunsplit((self.scheme, self.source, "r/jobs/q-%s" % query, "", ""))
            soup = PostingScraper._get_cleaned_soup_from_url(search_url)
            print soup
            job_search_results_div = soup.find('div', attrs=ElanceScraper._job_search_results_div_attrs)
            for job_card_div in job_search_results_div.findAll('div', attrs=ElanceScraper._job_result_card_div_attrs):
                url = job_card_div.find('a', attrs=ElanceScraper._job_card_url_attrs)
                print url
                postings.append(url)
            print postings
            return postings
        except Exception:
            traceback.print_exc(file=stderr)
            return []


class IndeedScraper(PostingScraper):
    _job_results_col_attrs = {"id": "resultsCol"}
    _job_row_result_div_attrs = {"class": re.compile(r"row.*result")}
    _job_location_span_attrs = {"class": "location"}
    _job_date_span_attrs = {"class": "date"}
    _job_description_span_attrs = {"itemprop": "description"}

    def __init__(self, location):
        PostingScraper.__init__(self, "http://www.indeed.com")
        self.location = location

    def _get_info_from_indeed_result(self, row_result_soup):
        posting = {}
        # url, title
        try:
            url_data = row_result_soup.find('a')
            posting['url'] = self._clean_post_url(url_data['href'])
            posting['title'] = PostingScraper._encode_unicode(url_data.text)
        except (AttributeError, KeyError):
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
            traceback.print_exc(file=stderr)
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
                traceback.print_exc(file=stderr)
                pass
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        # description
        try:
            posting['description'] = PostingScraper._encode_unicode(
                row_result_soup.find("span", IndeedScraper._job_description_span_attrs).text)
        except AttributeError:
            pass
        posting['source'] = self.source
        return posting

    def get_postings(self, query, pages=1):
        try:
            query = quote_plus(query)
            search_url = urlunsplit((self.scheme, self.source, "jobs",
                                     "q=%s&l=%s&sort=date&start=%d" % (query, self.location, (pages-1)*10), ""))
            soup = PostingScraper._get_cleaned_soup_from_url(search_url)
            job_results_td = soup.find('td', attrs=IndeedScraper._job_results_col_attrs)
            return map(self._get_info_from_indeed_result, job_results_td.findAll('div', IndeedScraper._job_row_result_div_attrs))
        except Exception:
            traceback.print_exc(file=stderr)
            return []


if __name__ == "__main__":
    scrapers = list()
    # scrapers.append(UpworkScraper())
    # scrapers.append(CraigslistScraper(base='baltimore'))
    # scrapers.append(GuruScraper())
    # scrapers.append(ElanceScraper())
    scrapers.append(IndeedScraper("baltimore"))
    for scraper in scrapers:
        print scraper
        for p in scraper.get_postings("computer thing"):
            for k, v in p.items():
                print k, " => ", v
