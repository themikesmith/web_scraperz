from urllib import quote_plus
import re
from super_dt_parser import safe_dt_parse
from posting_class import Posting
from posting_scraper import PostingScraper
from sys import stderr
from urlparse import urlsplit, urlunsplit
import traceback

__author__ = 'mcs'


class GuruScraper(PostingScraper):

    _job_search_results_list_attr = {"class": "services", "id": "serviceList"}
    _job_search_result_list_item_attrs = {"class": re.compile(r"^serviceItem")}
    _job_search_results_header_attrs = {"class": "servTitle"}
    _job_url_meta_attrs = {"property": "og:url"}
    _job_date_posted_span_attrs = {"class": "dt-style1"}
    _job_duration_span_attrs = {"id": "spnDurationLeft"}
    _job_budget_div_attrs = {"class": "budget"}
    _job_skill_section_attrs = {"id": "skillsSec"}
    _job_skill_link_attrs = {"class": "skillItem"}
    _job_experience_reqs_section_attrs = {"itemprop": "experienceRequirements"}
    _job_title_attrs = {"itemprop": "title"}

    def __init__(self):
        PostingScraper.__init__(self, "http://www.guru.com")

    def _get_info_from_guru_job_page_soup(self, posting_soup):
        posting = Posting({'source': self.source})
        # url, and unique id
        url = posting_soup.find('meta', attrs=GuruScraper._job_url_meta_attrs)
        if url is not None:
            posting['url'] = self._clean_post_url(url['content'])
            url_parts = urlsplit(posting['url'])
            if url_parts.path:
                sections = url_parts.path.rsplit('/')
                [sections.remove(s) for s in sections if not s]
                posting['unique_id'] = sections[-1]
        # title
        try:
            title_header = posting_soup.find(attrs=GuruScraper._job_title_attrs)
            posting['title'] = PostingScraper._encode_unicode(title_header.text)
        except AttributeError:
            pass
        # date posted
        try:
            date_posted_span = posting_soup.find('span', attrs=GuruScraper._job_date_posted_span_attrs)
            posting['date_posted'] = safe_dt_parse(date_posted_span['data-date'])
        except (KeyError, AttributeError, ValueError):
            # traceback.print_exc(file=stderr)
            pass
        # duration
        try:
            duration_span = posting_soup.find('span', attrs=GuruScraper._job_duration_span_attrs)
            actual_date_span = duration_span.find('span')
            posting['duration'] = safe_dt_parse(actual_date_span['data-date'])
        except (KeyError, AttributeError, ValueError, TypeError):
            # traceback.print_exc(file=stderr)
            pass
        # budget
        try:
            budget_div = posting_soup.find('div', attrs=GuruScraper._job_budget_div_attrs)
            posting['budget'] = PostingScraper._encode_unicode(budget_div.text)
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        # skills
        try:
            skills_section = posting_soup.find(attrs=GuruScraper._job_skill_section_attrs)
            posting['skills'] = map(lambda x:
                                    PostingScraper._encode_unicode(PostingScraper._get_cleaned_soup_from_html(x).text),
                                    skills_section.find('a', attrs=GuruScraper._job_skill_link_attrs))
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        # experience, desription
        try:
            description_section = posting_soup.find(attrs=GuruScraper._job_experience_reqs_section_attrs)
            posting['description'] = PostingScraper._encode_unicode(
                PostingScraper._get_cleaned_soup_from_html(str(description_section)).text)
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        return posting

    def get_postings(self, query, pages=1):
        postings = []
        try:
            query = re.sub(' ', '-', query)  # funny syntax for guru website
            query = quote_plus(query)
            for page_num in range(1, pages + 1):
                search_url = urlunsplit((self.scheme, self.source, "d/jobs/q/%s/pg/%d" % (query, page_num), "", ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                services_list = soup.find(attrs=GuruScraper._job_search_results_list_attr)
                try:  # handle if there are more pages than results... services_list won't exist
                    for i, li in enumerate(services_list.findAll('li', attrs=GuruScraper._job_search_result_list_item_attrs)):
                        h2 = li.find('h2', attrs=GuruScraper._job_search_results_header_attrs)
                        a = h2.find('a')
                        postings.append(self._clean_post_url(a['href']))
                except (AttributeError, TypeError, KeyError):
                    # also handle misc errors, want to gracefully return postings we already have
                    # traceback.print_exc(file=stderr)
                    pass
            return list(set(PostingScraper._remove_none_from_things(
                map(self._get_info_from_guru_job_page_soup,
                    map(PostingScraper._get_cleaned_soup_from_url, postings)))))
        except Exception:
            traceback.print_exc(file=stderr)
            return []