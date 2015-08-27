from urlparse import urlsplit, urlunsplit
from BeautifulSoup import BeautifulSoup, Comment
from HTMLParser import HTMLParser
import requests


class PostingScraper(object):
    """
    Interface for scrapers for posting websites.
    Implements "get postings" from a 'base url' construct
    """

    _html_parser = HTMLParser()

    def __init__(self, base):
        """
        initialize the scraper with a base url, and a source
        """
        r = urlsplit(base)
        self.scheme = r.scheme
        self.source = r.netloc

    @staticmethod
    def _encode_unicode(s):
        return s.encode('utf8')

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
        html = unicode(html, "utf-8")
        soup = BeautifulSoup(PostingScraper._html_parser.unescape(html))
        # soup = BeautifulSoup(html, "html.parser")
        # get rid of all HTML comments, as they show up in soup's .text results
        comments = soup.findAll(text=lambda x: isinstance(x, Comment))
        # comments = soup.find_all(text=lambda x: isinstance(x, Comment))
        [comment.extract() for comment in comments]
        return soup

    @staticmethod
    def _get_cleaned_soup_from_url(url):
        """
        Return BeautifulSoup object with comments removed from url.
        :param url: the url to request
        :return: the resulting BeautifulSoup object
        """
        text = requests.get(url).text
        return PostingScraper._get_cleaned_soup_from_html(text)

    def get_postings(self, query, pages=1):
        """
        Gather results given a query and the number of pages desired.
        A posting is a dict with the following attributes:
            - url
            - price
            - location: state, city, country
            - text
            - unique id
            - date created
        Will be different for each website (duh)
        :param query: query to use on the site
        :param pages: number of pages of results desired
        :return: a list of postings, each of which is a dict.
        """
        raise NotImplementedError("Should have implemented this")
