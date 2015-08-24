__author__ = 'mcs'

import requests
from HTMLParser import HTMLParser
from time import sleep
from pyvirtualdisplay import Display
from contextlib import closing
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from BeautifulSoup import BeautifulSoup, Comment


html_parser = HTMLParser()


def get_cleaned_soup_from_url(url, dynamic=False, id_to_wait_for=None):
    """
    Given a url, whether it has dynamic content or not,
    and if it does have dynamic content, an ID to wait for loading,
    make the request, process the HTML into BeautifulSoup, return
    :param url: the url to request
    :param dynamic: True if URL contains dynamic content, false otherwise
    :param id_to_wait_for: an ID of an object on the page to wait for loading, used if dynamic
    :return: the resulting BeautifulSoup object
    """
    if not dynamic:
        r = requests.get(url)
        text = r.text
    else:
        # set up a web scraping session
        # code to virtual display, for firefox, set not visible! pseudo-headless fuck yeah
        display = Display(visible=0, size=(800, 600))
        display.start()
        with closing(webdriver.Firefox()) as browser:
            browser.set_page_load_timeout(15)
            for i in xrange(3):  # try three times
                try:
                    browser.get(url)  # potentially can trigger timeout too? put in try clause just in case
                    if id_to_wait_for is not None:
                        WebDriverWait(browser, timeout=15).until(
                            lambda x: x.find_element_by_id(id_to_wait_for)
                        )  # can trigger timeout
                    break
                except TimeoutException:
                    browser.close()
                    sleep(2)
            text = browser.page_source
        display.stop()
    soup = BeautifulSoup(html_parser.unescape(text))
    # get rid of all HTML comments, as they show up in soup's .text results
    comments = soup.findAll(text=lambda x: isinstance(x, Comment))
    [comment.extract() for comment in comments]
    return soup
