from urllib import quote_plus
from urlparse import urlsplit, urlunsplit
import re
import geocoder
from dateutil import parser as dt_parser

import posting_scraper


class CraigslistScraper(posting_scraper.PostingScraper):
    # Data isn't loaded via JS, Selenium isn't requried.

    def __init__(self, base):
        # Base is either the full craigslist URL or the craigslist subdomain.
        # Examples: "http://baltimore.craigslist.org" or just "baltimore"
        if not base.endswith('.craigslist.org'):
            base = 'http://%s.craigslist.org' % base
        super(CraigslistScraper, self).__init__(base)

    def _get_info_from_clp_posting(self, url):
        posting = {}
        soup = self._get_cleaned_soup_from_url(url)
        posting['url'] = url
        try:
            loc = soup.find(href=re.compile("google.com/maps"))['href']
            g = geocoder.google(loc[loc.find('@')+1:-1].split(',')[:-1], method='reverse')
            posting['state'] = g.state
            posting['city'] = g.city
            posting['country'] = g.country
        except Exception as e:  # What are the possible exceptions here? They need some logging.
            print 'Excepted', e
        try:
            posting['price'] = soup.find(text=re.compile('.*compensation.*')).parent.findChild('b').text.replace('$', '')
        except:
            pass
        try:
            posting['text'] = soup.find('section', {'id': 'postingbody'}).text
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
        query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
        posts = []  # temporary variable to store all of the posting data
        for i in range(1, pages + 1):
            search_url = urlunsplit((self.scheme, self.source, "/search/ggg",
                                     "query=%s&sort=date?s=%d" % (query, pages*100), ""))
            soup = self._get_cleaned_soup_from_url(search_url)
            posts += [self._clean_post_url(a['href']) for a in soup.findAll('a', {'data-id': re.compile('\d+')})]
            # posts += [self._clean_post_url(a['href']) for a in soup.find_all('a', {'data-id': re.compile('\d+')})]
        return [self._get_info_from_clp_posting(post) for post in posts]


class UpworkScraper(posting_scraper.PostingScraper):
    # They have an API, nicer on their servers and prevents headaches when
    # formatting changes.
    # https://developers.upwork.com/?lang=python#introduction

    _job_search_result_link_attrs = {"class": "break", "itemprop": "url"}
    _job_url_attrs = {"property": "og:url"}
    _job_container_attrs = {"class": "container", "itemtype": "http://schema.org/JobPosting"}
    _job_dateposted_attrs = {"itemprop": "datePosted"}
    _job_descrip_aircard_attrs = {"class": "air-card-group"}
    _job_skill_tag_attrs = {"class": re.compile("^o-tag-skill")}
    _div_row_attrs = {'class': 'row'}

    def __init__(self):
        super(UpworkScraper, self).__init__("http://www.upwork.com")

    def _get_info_from_upwork_posting(self, posting_soup):
        """
        Given an Upwork article HTML object, extract the desired information and return as a dict
        :param posting_soup: the Soup-ed HTML
        :return: the data in a dict
        """
        posting = {}
        try:
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
                posting['date_created'] = dt_parser.parse(date_posted_span['popover'])
            except KeyError:  # thrown if no 'popover' attribute
                pass
            # price
            # second row of container, first element, first row inside that
            try:
                second_row = container.findAll('div', attrs=UpworkScraper._div_row_attrs)[1]
                try:
                    first_child = second_row.find('div')
                    price_row = first_child.find('div', attrs=UpworkScraper._div_row_attrs)
                    try:
                        posting['price_info'] = self._encode_unicode(price_row.text)
                    except AttributeError:  # thrown if price_row is None
                        pass
                except IndexError:  # thrown if second_row doesn't have a first_child
                    pass
            except IndexError:  # thrown if container doesn't have a second 'row' tag
                pass
            # text
            try:
                description_air_card = container.find('div', attrs=UpworkScraper._job_descrip_aircard_attrs)
                posting['description'] = self._encode_unicode(description_air_card.find('p').text)
            except AttributeError:  # handle if soup finds nothing
                pass
            # skills
            try:
                posting['skills'] = map(lambda x: self._encode_unicode(x.text),
                                        container.findAll('a', attrs=UpworkScraper._job_skill_tag_attrs))
            except AttributeError:  # handle if soup finds nothing for skills
                pass
            # unique id
            posting['source'] = self.source
        except Exception as e:
            print e
        return posting

    def get_postings(self, query, pages=1):
        query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
        posts = []
        # example url:
        # https://www.upwork.com/o/jobs/browse/?q=therapist
        for i in range(1, pages + 1):
            search_url = urlunsplit((self.scheme, self.source, "/o/jobs/browse/", "page=%d&q=%s" % (i, query), ""))
            soup = self._get_cleaned_soup_from_url(search_url)
            # print soup
            # this url returns a list of postings of profiles. visit each profile
            for article in soup.findAll('article'):  # get all 'article'
                url = article.find('a', attrs=UpworkScraper._job_search_result_link_attrs)
                posts.append(self._clean_post_url(url['href']))
        return map(self._get_info_from_upwork_posting,
                   map(self._get_cleaned_soup_from_url, posts))


class GuruScraper(posting_scraper.PostingScraper):
    # Data isn't loaded via JS, Selenium isn't requried.

    _job_search_results_list_attr = {"class": "services", "id": "serviceList"}
    _job_search_result_list_item_attrs = {"class": re.compile(r"^serviceItem")}
    _job_search_results_header_attrs = {"class": "servTitle"}

    def __init__(self):
        super(GuruScraper, self).__init__("http://www.guru.com")

    def _get_info_from_guru_job_page_soup(self, job_page_soup):
        posting = {}
        try:
            pass
        except Exception as e:
            print e
        return posting

    def get_postings(self, query, pages=1):
        postings = []
        query = re.sub(' ', '-', query)  # funny syntax for guru website
        query = quote_plus(query)
        search_url = urlunsplit((self.scheme, self.source, "d/jobs/q/%s/" % query, "", ""))
        soup = self._get_cleaned_soup_from_url(search_url)
        services_list = soup.find(attrs=GuruScraper._job_search_results_list_attr)
        for i, li in enumerate(services_list.findAll('li', attrs=GuruScraper._job_search_result_list_item_attrs)):
            h2 = li.find('h2', attrs=GuruScraper._job_search_results_header_attrs)
            a = h2.find('a')
            postings.append(self._clean_post_url(a['href']))
        return map(self._get_info_from_guru_job_page_soup,
                   map(self._get_cleaned_soup_from_url, postings))


if __name__ == "__main__":
    # u = UpworkScraper()
    # for p in u.get_postings("therapist"):
    #     for k, v in p.items():
    #         print k, ": ", v
    # c = CraigslistScraper(base='baltimore')
    # for p in c.get_postings("massage therapist"):
    #     for k, v in p.items():
    #         print k, ": ", v
    g = GuruScraper()
    for p in g.get_postings("computer thing"):
        print p
