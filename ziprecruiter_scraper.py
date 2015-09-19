from urllib import quote_plus
import re
import geocoder
from super_dt_parser import safe_dt_parse
from posting_class import Posting
from posting_scraper import PostingScraper
from sys import stderr
from urlparse import urlsplit, urlunsplit, parse_qs
import traceback

__author__ = 'mcs'


class ZipRecruiterScraper(PostingScraper):
    _job_list_div_attrs = {"id": "job_list"}
    _job_result_link_attrs = {"class": "job_link"}
    _job_posting_h1_title_attrs = {"itemprop": "title"}
    _job_posting_ogurl_attrs = {"property": "og:url"}
    _job_posting_p_date_posted_attrs = {"class": re.compile(r"^[Pp]osted.*")}
    _job_posting_div_description_attrs = {"itemprop": "description"}
    _job_posting_latlong_attrs = {"name": "geo.position"}
    _job_posting_locdiv_attrs = {"itemprop": "jobLocation"}

    def __init__(self, location=""):
        PostingScraper.__init__(self, "http://www.ziprecruiter.com")
        if location:
            self.location = location
        else:
            self.location = ""

    def get_postings(self, query, pages=1):
        try:
            postings = []
            query = quote_plus(query)
            for page_num in range(1, pages+1):
                # https://www.ziprecruiter.com/candidate/search?sort=best-match&search=writer&page=2&location=baltimore
                search_url = urlunsplit((self.scheme, self.source, "candidate/search",
                                         "sort=best-match&search=%s&location=%s&page=%d" %
                                         (query, quote_plus(self.location.lower()), page_num), ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                job_results_list_div = soup.find('div', attrs=ZipRecruiterScraper._job_list_div_attrs)
                try:
                    postings.extend(map(lambda x: x['href'],
                                        job_results_list_div.findAll('a', ZipRecruiterScraper._job_result_link_attrs)))
                except AttributeError:
                    # traceback.print_exc(file=stderr)
                    pass
            # note that we could return None if we go to an external url here
            postings = map(self._get_info_from_ziprecruiter_result, postings)
            return list(set(PostingScraper._remove_none_from_things(postings)))
        except Exception:
            traceback.print_exc(file=stderr)
            return []

    def _get_info_from_ziprecruiter_result(self, job_link):
        # print >> stderr, job_link
        soup = PostingScraper._get_cleaned_soup_from_url(job_link)
        if not len(soup):
            # print >> stderr, "returning none, soup false, link:%s" % job_link
            return None
        posting = Posting()
        # url
        try:
            url_meta = soup.find('meta', attrs=ZipRecruiterScraper._job_posting_ogurl_attrs)
            url = url_meta['content']
            posting.add_url(url)
            # id is the last series of alphanumeric characters after the last hyphen in the url path
            # e.g., /jobs/proedit-inc-18374379/contract-scientific-writer-2ccbf90f
            # would mean 2ccbf90f
            things = urlsplit(url)
            path = things[2]
            last_hyphen = path.rfind('-')
            if last_hyphen != -1:
                # print >> stderr, path[last_hyphen+1:]
                posting.add_id(path[last_hyphen+1:])
            else:
                # just take the whole url after the base
                # print >> stderr, "couldn't find id in url:%s" % url
                # print >> stderr, "making id:", path
                posting.add_id(path)
        except (TypeError, IndexError):
            # traceback.print_exc(file=stderr)
            pass
        # source
        posting.add_source(self.source)
        # title
        try:
            title_h1 = soup.find('h1', attrs=ZipRecruiterScraper._job_posting_h1_title_attrs)
            posting.add_title(PostingScraper._encode_unicode(title_h1.text))
        except AttributeError:  # if title_h1 is None
            # traceback.print_exc(file=stderr)
            pass
        # location
        try:
            # try to do the following first, more exact
            geoloc_meta = soup.find('meta', attrs=ZipRecruiterScraper._job_posting_latlong_attrs)['content']
            geoloc_meta = re.sub(";", ",", geoloc_meta)
            g = geocoder.google(geoloc_meta.split(','), method='reverse')
            # print >> stderr, "reverse by latlong, loc:%s => g:%s" % (geoloc_meta, str(g))
            posting['state'] = g.state
            posting['city'] = g.city
            posting['country'] = g.country
        except (TypeError, AttributeError, KeyError):
            # try to find the google map link
            try:
                maps_url = soup.find(href=re.compile(r"google\.com/maps|maps\.google\.com"))['href']
                things = urlsplit(maps_url)
                params = things[3]
                loc = parse_qs(params)
                loc_str = loc['q'][0]
                g = geocoder.google(loc_str)
                # print >> stderr, "normal by loc:%s => g:%s" % (loc_str, g)
                posting['state'] = g.state
                posting['city'] = g.city
                posting['country'] = g.country
            except (TypeError, AttributeError, KeyError, IndexError):
                # traceback.print_exc(file=stderr)
                pass
        # date posted
        try:
            try:  # try this first, but if we fail...
                date_posted_p = soup.find('p', attrs=ZipRecruiterScraper._job_posting_p_date_posted_attrs)
                # find first 'span'
                date_posted_span = date_posted_p.find('span')
                dt_text = re.sub(r"[Pp]osted", "", date_posted_span.text.lower()).strip()
                posting.add_date_posted(safe_dt_parse(dt_text))
            except AttributeError:
                try:
                    # ... double-check that we have a 'posted today / this week / 12 hours ago / whatever'
                    locdiv = soup.find('div', attrs=ZipRecruiterScraper._job_posting_locdiv_attrs)
                    header_div = locdiv.parent
                    date_p = header_div.findAll('p')[-1]
                    date_span = date_p.find('span')
                    date_span_text = date_span.text.lower()
                    if "posted" in date_span_text:
                        # and if so, take appropriate action
                        dt_text = re.sub(r"posted", "", date_span_text).strip()
                        posting.add_date_posted(safe_dt_parse(dt_text))
                    else:
                        # print >> stderr, "don't have a date found at url:%s" % job_link
                        pass
                except (AttributeError, IndexError):
                    # traceback.print_exc(file=stderr)
                    pass
        except ValueError as e:
            print >> stderr, "error parsing date posted string at url:%s" % job_link
            pass
        # description
        try:
            description_div = soup.find('div', attrs=ZipRecruiterScraper._job_posting_div_description_attrs)
            posting.add_description(PostingScraper._encode_unicode(description_div.text))
        except AttributeError:
            # traceback.print_exc(file=stderr)
            pass
        return posting
