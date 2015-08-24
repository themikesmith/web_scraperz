from urllib import quote_plus
import re
import geocoder
from super_requests import get_html_from_url
from BeautifulSoup import BeautifulSoup, Comment
from HTMLParser import HTMLParser



html_parser = HTMLParser()


class PostingScraper:
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
        soup = BeautifulSoup(html_parser.unescape(text))
        # get rid of all HTML comments, as they show up in soup's .text results
        comments = soup.findAll(text=lambda x: isinstance(x, Comment))
        [comment.extract() for comment in comments]
        return soup

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
        print posts
        return [CraigslistScraper._get_info_from_clp_posting(post) for post in posts]


class UpworkScraper(PostingScraper):
    def __init__(self):
        PostingScraper.__init__(self, "http://www.upwork.com")
        # in query results, a profile link is a link with class="jsShortName"
        self._query_profile_link_class = "jsShortName"

    @staticmethod
    def _get_info_from_upwork_posting(profile_url):
        """
        Given an Upwork profile URL, extract the desired information and return as a dict
        :param profile_url: the profile URL
        :return: the data in a dict
        """
        # commented out old versions for reference
        # soup = PostingScraper._get_cleaned_soup_from_url(profile_url, dynamic=True, id_to_wait_for='oProfilePage')
        soup = PostingScraper._get_cleaned_soup_from_url(profile_url, dynamic=True)
        # soup = PostingScraper._get_cleaned_soup_from_url(profile_url)

        # url
        posting = dict(url=profile_url)
        # price
        posting['prices'] = map(lambda x: x.text, soup.findAll('span', attrs={"itemprop": "pricerange"}))
        # location: city, state, country
        posting['locations'] = []
        locations = map(lambda x: x.text, soup.findAll('h3', attrs={"itemprop": "address"}))
        for loc in locations:
            g = geocoder.google(loc)
            posting['locations'].append({"city": g.city, "state": g.state, "country": g.country})
        # text
        try:
            posting['description'] = soup.find('p', attrs={"itemprop": "description"}).text
        except AttributeError:  # handle if soup finds nothing
            pass
        # skills
        skills = soup.find('up-skills-public-viewer')
        try:
            posting['skills'] = map(lambda x: x.text, skills.findAll('a'))
        except AttributeError:  # handle if soup finds nothing
            pass
        # unique id
        # date created
        return posting

    def get_postings(self, query, pages=1):
        query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
        posts = []
        # example url:
        # http://www.upwork.com/o/profiles/browse/?q=massage%20therapist
        for i in range(1, pages + 1):
            search_url = self.base + "/o/profiles/browse/?page=%d&q=%s" % (i, query)
            soup = PostingScraper._get_cleaned_soup_from_url(search_url, dynamic=False)
            # this url returns a list of postings of profiles. visit each profile
            for article in soup.findAll('article'):  # get all 'article'
                # profile link is a link with class="jsShortName"
                urls = article.findAll('a', attrs={"class": self._query_profile_link_class})
                posts += map(lambda a: self._clean_post_url(a['href']), urls)
        return map(UpworkScraper._get_info_from_upwork_posting, posts)


if __name__ == "__main__":
    # u = UpworkScraper()
    # for p in u.get_postings("massage therapist"):
    #     print p
    c = CraigslistScraper(base='baltimore')
    for p in c.get_postings("massage therapist"):
        print p
