from urllib import quote_plus
import re
import geocoder
from super_requests import get_html_from_url
from BeautifulSoup import BeautifulSoup, Comment
from HTMLParser import HTMLParser


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

    _job_link_attrs = {"class": "break", "itemprop": "url"}
    _job_dateposted_attrs = {"itemprop": "datePosted"}
    _job_description_attrs = {"class": "description"}
    _job_skills_span_attrs = {"class": "js-skills skills"}
    _job_skill_tag_attrs = {"class": "o-tag-skill"}
    _job_price_div_attrs = {"class": "o-support-info m-sm-bottom m-sm-top"}
    _job_price_div_throwaway_attrs = {"class": "js-posted"}

    def __init__(self):
        PostingScraper.__init__(self, "http://www.upwork.com")
        # in query results, a profile link is a link with class="jsShortName"

    def _get_info_from_upwork_posting(self, article_soup):
        """
        Given an Upwork article HTML object, extract the desired information and return as a dict
        :param article_soup: the Soup-ed HTML
        :return: the data in a dict
        """
        posting = {}
        # url
        url = article_soup.find(attrs=UpworkScraper._job_link_attrs)
        if url is not None:
            posting['url'] = self._clean_post_url(url['href'])
        # date posted
        date_posted = article_soup.find(attrs=UpworkScraper._job_dateposted_attrs)
        posting['date_created'] = date_posted['datetime']
        # price
        price_div = article_soup.find(attrs=UpworkScraper._job_price_div_attrs)
        try:
            [x.extract() for x in price_div.findAll(attrs=UpworkScraper._job_price_div_throwaway_attrs)]
            posting['price_info'] = price_div.text
        except AttributeError:
            pass
        # text
        try:
            posting['description'] = article_soup.find('div', attrs=UpworkScraper._job_description_attrs).text
        except AttributeError:  # handle if soup finds nothing
            pass
        # skills
        skills = article_soup.find(attrs=UpworkScraper._job_skills_span_attrs)
        try:
            posting['skills'] = map(lambda x: x.text, skills.findAll('a', attrs=UpworkScraper._job_skill_tag_attrs))
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
                posts += PostingScraper._get_cleaned_soup_from_html(str(article))
        return map(self._get_info_from_upwork_posting, posts)


if __name__ == "__main__":
    u = UpworkScraper()
    for p in u.get_postings("therapist"):
        print p
    c = CraigslistScraper(base='baltimore')
    for p in c.get_postings("massage therapist"):
        print p
