from urllib import quote_plus
import re
import geocoder
from super_requests import get_html_from_url
from BeautifulSoup import BeautifulSoup, Comment
from HTMLParser import HTMLParser
from dateutil import parser as dt_parser


class PostingScraper:

    _html_parser = HTMLParser()

    """
    Interface for scrapers for posting websites.
    Implements "get postings" from a 'base url' construct
    """
    def __init__(self, base):
        """
        initialize the scraper with a base url
        """
        self.base = base

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
        if url[:2] == '//':
            return 'http:'+url
        elif url[0] == '/':
            return self.base + url
        return url

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

    @staticmethod
    def _get_info_from_clp_posting(url):
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
        return posting

    def get_postings(self, query, pages=1):
        query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
        posts = []  # temporary variable to store all of the posting data
        for i in range(1, pages + 1):
            search_url = self.base + '/search/ggg?query=%s&sort=date?s=%d' % (query, pages*100)
            soup = PostingScraper._get_cleaned_soup_from_url(search_url)
            posts += [self._clean_post_url(a['href']) for a in soup.findAll('a', {'data-id': re.compile('\d+')})]
            # posts += [self._clean_post_url(a['href']) for a in soup.find_all('a', {'data-id': re.compile('\d+')})]
        return [CraigslistScraper._get_info_from_clp_posting(post) for post in posts]


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
        # in query results, a profile link is a link with class="jsShortName"

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
                    posting['price_info'] = PostingScraper._encode_unicode(price_row.text)
                except AttributeError:  # thrown if price_row is None
                    pass
            except IndexError:  # thrown if second_row doesn't have a first_child
                pass
        except IndexError:  # thrown if container doesn't have a second 'row' tag
            pass
        # text
        try:
            description_air_card = container.find('div', attrs=UpworkScraper._job_descrip_aircard_attrs)
            posting['description'] = PostingScraper._encode_unicode(description_air_card.find('p').text)
        except AttributeError:  # handle if soup finds nothing
            pass
        # skills
        try:
            posting['skills'] = map(lambda x: PostingScraper._encode_unicode(x.text),
                                    container.findAll('a', attrs=UpworkScraper._job_skill_tag_attrs))
        except AttributeError:  # handle if soup finds nothing for skills
            pass
        # unique id
        # date created
        return posting

    def get_postings(self, query, pages=1):
        query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
        posts = []
        # example url:
        # https://www.upwork.com/o/jobs/browse/?q=therapist
        for i in range(1, pages + 1):
            search_url = self.base + "/o/jobs/browse/?page=%d&q=%s" % (i, query)
            soup = PostingScraper._get_cleaned_soup_from_url(search_url)
            # print soup
            # this url returns a list of postings of profiles. visit each profile
            for article in soup.findAll('article'):  # get all 'article'
                url = article.find('a', attrs=UpworkScraper._job_search_result_link_attrs)
                posts.append(self._clean_post_url(url['href']))
        return map(self._get_info_from_upwork_posting,
                   map(PostingScraper._get_cleaned_soup_from_url, posts))


if __name__ == "__main__":
    u = UpworkScraper()
    for p in u.get_postings("therapist"):
        for k, v in p.items():
            print k, ": ", v
    c = CraigslistScraper(base='baltimore')
    for p in c.get_postings("massage therapist"):
        for k, v in p.items():
            print k, ": ", v
