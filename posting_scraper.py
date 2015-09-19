from BeautifulSoup import BeautifulSoup, Comment
from HTMLParser import HTMLParser
from urlparse import urlsplit, urlunsplit
from super_requests import get_html_from_url
from sys import stderr
import traceback

__author__ = 'mcs'


class PostingScraper:
    """
    Interface for scrapers for posting websites.
    Implements "get postings" from a 'base url' construct
    """

    _html_parser = HTMLParser()

    def __init__(self, base):
        """
        initialize the scraper with a base url
        """
        r = urlsplit(base)
        self.scheme = r.scheme
        self.source = r.netloc

    @staticmethod
    def _encode_unicode(s):
        return s.encode('utf8')

    @staticmethod
    def _remove_none_from_things(provided_list):
        return [x for x in provided_list if x is not None]

    def _clean_post_url(self, url):
        """
        Cleans the url:
        - makes the scheme values uniform
        - adds the base url to any local urls
        :param url: the url to clean
        :return: the cleaned url
        """
        split_url = list(urlsplit(url))
        split_url[0] = self.scheme
        if not split_url[1]:
            split_url[1] = self.source
        split_url = tuple(split_url)
        return urlunsplit(split_url)

    @staticmethod
    def _get_cleaned_soup_from_html(html):
        # html = html.encode("utf8")
        soup = BeautifulSoup(PostingScraper._html_parser.unescape(html))
        # soup = BeautifulSoup(html, "html.parser")
        # get rid of all HTML comments, as they show up in soup's .text results
        comments = soup.findAll(text=lambda x: isinstance(x, Comment))
        # comments = soup.find_all(text=lambda x: isinstance(x, Comment))
        [comment.extract() for comment in comments]
        return soup

    @staticmethod
    def _get_cleaned_soup_from_url(url, dynamic=False, id_to_wait_for=None):
        """
        Wrapper for getting html from url, parse as BeautifulSoup, extract comments
        :param url: the url to request
        :param dynamic: True if URL contains dynamic content, false otherwise
        :param id_to_wait_for: an ID of an object on the page to wait for loading, used if dynamic
        :return: the resulting BeautifulSoup object
        """
        try:
            text = get_html_from_url(url, dynamic=dynamic, id_to_wait_for=id_to_wait_for)
        except ValueError:  # TODO: how handle if site times out or refuses connection?
            traceback.print_exc(file=stderr)
            text = ""  # just set blank if we can't get it for now.
        return PostingScraper._get_cleaned_soup_from_html(text)

    def get_postings(self, query, pages=1):
        """
        Gather results, given a query and the number of pages of results desired.
        A posting is a dict with the following minimum attributes:
            - text description
            - source
            - unique id
            - title
            - date posted
            - url
        Postings from websites may contain more information, e.g., price or location
        :param query: query to use on the site
        :param pages: number of pages of results desired
        :return: a list of postings, each of which is a dict.
        """
        raise NotImplementedError("Should have implemented this")
