from urllib import quote_plus
import re
import geocoder
from posting_class import Posting
from posting_scraper import PostingScraper
from sys import stderr
from urlparse import urlunsplit
import traceback

__author__ = 'mcs'


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
