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


class SimplyhiredScraper(PostingScraper):
    _job_results_list_div_attrs = {"class": "results"}
    _job_result_div_attrs = {"class": "job", "itemtype": re.compile(r"JobPosting")}
    _job_title_link_attrs = {"class": "title"}
    _job_tools_container_attrs = {"class": "tools_container"}
    _description_page_info_table_attrs = {"class": "info-table"}
    _description_page_description_attrs = {"class": "job-description"}
    _description_page_table_info_label_attrs = {"class": "info-label"}

    def __init__(self, location=""):
        PostingScraper.__init__(self, "http://www.simplyhired.com")
        if location:
            self.location = location
        else:
            self.location = ""

    def _get_info_from_simplyhired_result(self, result_soup):
        posting = Posting({'source': self.source})
        # external url, title
        try:
            title_link = result_soup.find('a', attrs=SimplyhiredScraper._job_title_link_attrs)
            posting['external_url'] = self._clean_post_url(title_link['href'])
            posting['title'] = PostingScraper._encode_unicode(title_link.text)
        except (AttributeError, KeyError, TypeError):
            # traceback.print_exc(file=stderr)
            pass
        # url
        description_page_url = None
        try:
            tools_container = result_soup.find('div', attrs=SimplyhiredScraper._job_tools_container_attrs)
            tools_links = tools_container.findAll('a')
            description_page_url = tools_links[-1]['href']
            posting['url'] = description_page_url
            posting['unique_id'] = description_page_url  # TODO i couldn't actually find a unique id?
        except (KeyError, AttributeError, IndexError):
            # traceback.print_exc(file=stderr)
            pass
        if description_page_url is not None:
            # follow posting url to long description, and date posted
            description_page_soup = PostingScraper._get_cleaned_soup_from_url(description_page_url)
            try:
                info_table = description_page_soup.find('table',
                                                        attrs=SimplyhiredScraper._description_page_info_table_attrs)
                # 4 rows: Company, Location, Date Posted, Source
                row_data_two = []
                trs = info_table.findAll('tr')
                for tr in trs:
                    tds = tr.findAll('td')
                    try:
                        last_td = tds[-1]
                        row_data_two.append(PostingScraper._encode_unicode(last_td.text))
                    except IndexError:
                        # traceback.print_exc(file=stderr)
                        pass
                info_labels = info_table.findAll('td', attrs=SimplyhiredScraper._description_page_table_info_label_attrs)
                info_labels = map(lambda x: PostingScraper._encode_unicode(x.text).lower(), info_labels)
                table_data = zip(info_labels, row_data_two)
                for label, value in table_data:
                    if not value.strip():
                        continue
                    if 'location' in label:
                        try:
                            g = geocoder.google(value, method='reverse')
                            posting['location'] = (g.city, g.state, g.country)
                        except Exception:
                            # traceback.print_exc(file=stderr)
                            pass
                    elif 'date posted' in label:
                        try:
                            posting['date_posted'] = safe_dt_parse(value)
                        except (AttributeError, ValueError):
                            # traceback.print_exc(file=stderr)
                            pass
                    elif 'source' in label:
                        posting['external_source'] = value
                    elif 'company' in label:
                        posting['company'] = value
            except AttributeError:
                # traceback.print_exc(file=stderr)
                pass
            # description
            try:
                description_div = description_page_soup.find('div', attrs=SimplyhiredScraper._description_page_description_attrs)
                posting['description'] = PostingScraper._encode_unicode(description_div.text)
            except AttributeError:
                # traceback.print_exc(file=stderr)
                pass
        return posting

    def get_postings(self, query, pages=1):
        try:
            postings = []
            query = quote_plus(query)
            for page_num in range(1, pages+1):
                # https://www.simplyhired.com/search?q=massage+therapist&l=baltimore%2C+md&pn=2
                search_url = urlunsplit((self.scheme, self.source, "search",
                                         "q=%s&l=%s&pn=%d" % (query, quote_plus(self.location.lower()), page_num), ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                job_results_list_div = soup.find('div', attrs=SimplyhiredScraper._job_results_list_div_attrs)
                try:
                    postings.extend(job_results_list_div.findAll('div', SimplyhiredScraper._job_result_div_attrs))
                except AttributeError:
                    # traceback.print_exc(file=stderr)
                    pass
            return list(set(PostingScraper._remove_none_from_things(
                map(self._get_info_from_simplyhired_result, postings))))
        except Exception:
            traceback.print_exc(file=stderr)
            return []
