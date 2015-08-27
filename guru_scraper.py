from urllib import quote_plus
from urlparse import urlunsplit
import re
import sys

import posting_scraper


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


def main(args):
    query = " ".join(args) if args else 'computer thing'
    g = GuruScraper()
    for p in g.get_postings(query):
        print p


if __name__ == "__main__":
    main(sys.argv)
