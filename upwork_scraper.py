from urllib import quote_plus
import re
from super_dt_parser import safe_dt_parse
from posting_class import Posting
from posting_scraper import PostingScraper
from sys import stderr
from urlparse import urlsplit, urlunsplit
import traceback

__author__ = 'mcs'


class UpworkScraper(PostingScraper):

    _job_search_result_link_attrs = {"class": "break", "itemprop": "url"}
    _job_url_attrs = {"property": "og:url"}
    _job_container_attrs = {"class": "container", "itemtype": "http://schema.org/JobPosting"}
    _job_dateposted_attrs = {"itemprop": "datePosted"}
    _job_descrip_aircard_attrs = {"class": "air-card-group"}
    _job_skill_tag_attrs = {"class": re.compile("^o-tag-skill")}
    _div_row_attrs = {'class': 'row'}

    def __init__(self):
        PostingScraper.__init__(self, "http://www.upwork.com")

    def _get_info_from_upwork_posting(self, posting_soup):
        """
        Given an Upwork article HTML object, extract the desired information and return as a dict
        :param posting_soup: the Soup-ed HTML
        :return: the data in a dict
        """
        posting = Posting({'source': self.source})
        # url
        try:
            url = posting_soup.find('meta', attrs=UpworkScraper._job_url_attrs)
            if url is not None:
                posting['url'] = self._clean_post_url(url['content'])
                posting['title'] = PostingScraper._encode_unicode(url.text)
                url_parts = urlsplit(posting['url'])
                if url_parts.path:
                    sections = url_parts.path.rsplit('/')
                    [sections.remove(s) for s in sections if not s]
                    posting['unique_id'] = sections[-1]
        except (KeyError, AttributeError):
            # traceback.print_exc(file=stderr)
            pass
        container = posting_soup.find(attrs=UpworkScraper._job_container_attrs)
        # date posted
        date_posted_span = container.find(attrs=UpworkScraper._job_dateposted_attrs)
        try:  # it's in the 'popover' attribute
            posting['date_posted'] = safe_dt_parse(date_posted_span['popover'])
        except (KeyError, AttributeError, ValueError, TypeError):
            # traceback.print_exc(file=stderr)
            pass
        # price
        # second row of container, first element, first row inside that
        try:
            second_row = container.findAll('div', attrs=UpworkScraper._div_row_attrs)[1]
            try:
                first_child = second_row.find('div')
                price_row = first_child.find('div', attrs=UpworkScraper._div_row_attrs)
                try:
                    posting['price_info'] = PostingScraper._encode_unicode(price_row.text)
                except AttributeError:  # thrown if price_row is None
                    # traceback.print_exc(file=stderr)
                    pass
            except IndexError:  # thrown if second_row doesn't have a first_child
                # traceback.print_exc(file=stderr)
                pass
        except IndexError:  # thrown if container doesn't have a second 'row' tag
            # traceback.print_exc(file=stderr)
            pass
        # text
        try:
            description_air_card = container.find('div', attrs=UpworkScraper._job_descrip_aircard_attrs)
            posting['description'] = PostingScraper._encode_unicode(description_air_card.find('p').text)
        except AttributeError:  # handle if soup finds nothing
            # traceback.print_exc(file=stderr)
            pass
        # skills
        try:
            posting['skills'] = map(lambda x: PostingScraper._encode_unicode(x.text),
                                    container.findAll('a', attrs=UpworkScraper._job_skill_tag_attrs))
        except AttributeError:  # handle if soup finds nothing for skills
            pass
        # unique id
        return posting

    def get_postings(self, query, pages=1):
        try:
            query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
            posts = []
            # example url:
            # https://www.upwork.com/o/jobs/browse/?q=therapist
            for i in range(1, pages + 1):
                search_url = urlunsplit((self.scheme, self.source, "/o/jobs/browse/", "page=%d&q=%s" % (i, query), ""))
                print >> stderr, search_url
                soup = PostingScraper._get_cleaned_soup_from_url(search_url)
                # this url returns a list of postings of profiles. visit each profile
                for article in soup.findAll('article'):  # get all 'article'
                    url = article.find('a', attrs=UpworkScraper._job_search_result_link_attrs)
                    try:
                        posts.append(self._clean_post_url(url['href']))
                    except (TypeError, KeyError):
                        pass
            return list(set(PostingScraper._remove_none_from_things(
                map(self._get_info_from_upwork_posting,
                    map(PostingScraper._get_cleaned_soup_from_url, posts)))))
        except Exception:
            traceback.print_exc(file=stderr)
            return []
