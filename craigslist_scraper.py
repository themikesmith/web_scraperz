from urllib import quote_plus
from urlparse import urlunsplit
import re
import sys
import geocoder

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


def main(args):
    query = ' '.join(args) if args else 'massage therapist'
    print 'searching for query "%s"' % query
    c = CraigslistScraper(base='baltimore')
    for p in c.get_postings("massage therapist"):
        for k, v in p.items():
            print k, ": ", v


if __name__ == "__main__":
    main(sys.argv[1:])
