from urllib import quote_plus
from urlparse import urlsplit, urlunsplit
import re
from dateutil import parser as dt_parser

import posting_scraper


class UpworkScraper(posting_scraper.PostingScraper):
    # They have an API, nicer on their servers and prevents headaches when
    # formatting changes.
    # https://developers.upwork.com/?lang=python#introduction

    _job_search_result_link_attrs = {"class": "break", "itemprop": "url"}
    _job_url_attrs = {"property": "og:url"}
    _job_container_attrs = {"class": "container", "itemtype": "http://schema.org/JobPosting"}
    _job_dateposted_attrs = {"itemprop": "datePosted"}
    _job_descrip_aircard_attrs = {"class": "air-card-group"}
    _job_skill_tag_attrs = {"class": re.compile("^o-tag-skill")}
    _div_row_attrs = {'class': 'row'}

    def __init__(self):
        super(UpworkScraper, self).__init__("http://www.upwork.com")

    def _get_info_from_upwork_posting(self, posting_soup):
        """
        Given an Upwork article HTML object, extract the desired information and return as a dict
        :param posting_soup: the Soup-ed HTML
        :return: the data in a dict
        """
        posting = {}
        try:
            # url
            url = posting_soup.find('meta', attrs=UpworkScraper._job_url_attrs)
            if url is not None:
                posting['url'] = self._clean_post_url(url['content'])
                url_parts = urlsplit(posting['url'])
                if url_parts.path:
                    sections = url_parts.path.rsplit('/')
                    [sections.remove(s) for s in sections if not s]
                    posting['unique_id'] = sections[-1]
            container = posting_soup.find(attrs=UpworkScraper._job_container_attrs)
            # date posted
            date_posted_span = container.find(attrs=UpworkScraper._job_dateposted_attrs)
            try:  # it's in the 'popover' attribute
                posting['date_created'] = dt_parser.parse(date_posted_span['popover'])
            except KeyError:  # thrown if no 'popover' attribute
                pass
            # price
            # second row of container, first element, first row inside that
            try:
                second_row = container.findAll('div', attrs=UpworkScraper._div_row_attrs)[1]
                try:
                    first_child = second_row.find('div')
                    price_row = first_child.find('div', attrs=UpworkScraper._div_row_attrs)
                    try:
                        posting['price_info'] = self._encode_unicode(price_row.text)
                    except AttributeError:  # thrown if price_row is None
                        pass
                except IndexError:  # thrown if second_row doesn't have a first_child
                    pass
            except IndexError:  # thrown if container doesn't have a second 'row' tag
                pass
            # text
            try:
                description_air_card = container.find('div', attrs=UpworkScraper._job_descrip_aircard_attrs)
                posting['description'] = self._encode_unicode(description_air_card.find('p').text)
            except AttributeError:  # handle if soup finds nothing
                pass
            # skills
            try:
                posting['skills'] = map(lambda x: self._encode_unicode(x.text),
                                        container.findAll('a', attrs=UpworkScraper._job_skill_tag_attrs))
            except AttributeError:  # handle if soup finds nothing for skills
                pass
            # unique id
            posting['source'] = self.source
        except Exception as e:
            print e
        return posting

    def get_postings(self, query, pages=1):
        query = quote_plus(query)  # don't use urlencode, some sites depend on argument order
        posts = []
        # example url:
        # https://www.upwork.com/o/jobs/browse/?q=therapist
        for i in range(1, pages + 1):
            search_url = urlunsplit((self.scheme, self.source, "/o/jobs/browse/", "page=%d&q=%s" % (i, query), ""))
            soup = self._get_cleaned_soup_from_url(search_url)
            # print soup
            # this url returns a list of postings of profiles. visit each profile
            for article in soup.findAll('article'):  # get all 'article'
                url = article.find('a', attrs=UpworkScraper._job_search_result_link_attrs)
                posts.append(self._clean_post_url(url['href']))
        return map(self._get_info_from_upwork_posting,
                   map(self._get_cleaned_soup_from_url, posts))


if __name__ == "__main__":
    pass
    # u = UpworkScraper()
    # for p in u.get_postings("therapist"):
    #     for k, v in p.items():
    #         print k, ": ", v
    # c = CraigslistScraper(base='baltimore')
    # for p in c.get_postings("massage therapist"):
    #     for k, v in p.items():
    #         print k, ": ", v
