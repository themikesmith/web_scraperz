# from datetime import datetime
import requests
import re
import geocoder
from BeautifulSoup import BeautifulSoup
from HTMLParser import HTMLParser


h = HTMLParser()


class CraigslistScraper:
    def __init__(self, base):
        if base == 'baltimore':
            self.base = 'http://baltimore.craigslist.org'

    @staticmethod
    def _get_info_from_clp_posting(url):
        posting = {}
        r = requests.get(url)
        soup = BeautifulSoup(h.unescape(r.text))
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

    def _clean_post_url(self, url):
        if url[:2] == '//':
            return 'http:'+url
        elif url[0] == '/':
            return self.base + url
        return url

    def get_postings(self, query, pages=1):
        posts = []
        # temporary variable to store all of the posting data
        for i in range(1, pages + 1):
            r = requests.get(self.base + '/search/ggg?query=%s&sort=date?s=%d' % (query, pages*100))
            soup = BeautifulSoup(r.text)
            posts += [self._clean_post_url(a['href']) for a in soup.findAll('a', {'data-id': re.compile('\d+')})]
        return [CraigslistScraper._get_info_from_clp_posting(post) for post in posts]
