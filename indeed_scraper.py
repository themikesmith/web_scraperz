from urllib import quote_plus
import re
import geocoder
from super_dt_parser import safe_dt_parse
from posting_class import Posting
from posting_scraper import PostingScraper
from sys import stderr
from urlparse import urlunsplit
import traceback

__author__ = 'mcs'


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
