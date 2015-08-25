__author__ = 'mcs'

import requests
from time import sleep
from pyvirtualdisplay import Display
# from contextlib import closing
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
import errno
from socket import error as socket_error
from sys import stderr


def _sleep_retry_print_helper(num_secs):
    print >> stderr, "sleeping, trying again in %d secs" % num_secs
    sleep(num_secs)


def _safe_browser_close(browser):
    try:
        browser.close()
    except socket_error:
        pass


def get_html_from_url(url, dynamic=False, id_to_wait_for=None):
    """
    Given a url, whether it has dynamic content or not,
    and if it does have dynamic content, an ID to wait for loading,
    make the request, process the HTML into BeautifulSoup, return
    Raises ValueError if couldn't get the text (whether due to timeouts or connections refused, etc)
    :param url: the url to request
    :param dynamic: True if URL contains dynamic content, false otherwise
    :param id_to_wait_for: an ID of an object on the page to wait for loading, used if dynamic
    :return: the HTML rendered
    """
    text = None
    if not dynamic:  # use requests
        for i in xrange(5):
            try:
                r = requests.get(url)
                text = r.text
                break
            except requests.exceptions.RequestException as e:
                print >> stderr, e
                _sleep_retry_print_helper(5)  # retry

    else:  # use selenium
        # code for virtual display, for firefox, set not visible! pseudo-headless fuck yeah
        display = Display(visible=0, size=(800, 600))
        display.start()
        # with closing(webdriver.Firefox()) as browser:
        if True:
            browser = webdriver.Firefox()
            browser.set_page_load_timeout(15)
            for i in xrange(5):  # try at most five times
                try:
                    browser.get(url)  # potentially can trigger timeout too? put in try clause just in case
                    if id_to_wait_for is not None:
                        WebDriverWait(browser, timeout=15).until(
                            lambda x: x.find_element_by_id(id_to_wait_for)
                        )  # can trigger timeout
                    text = browser.page_source
                    # sleep(1)  # add this in to avoid overtaxing servers
                    break  # ... if we get what we want
                except TimeoutException:  # if we get a timeout in webdriverwait, try again in 5 seconds
                    _safe_browser_close(browser)
                    _sleep_retry_print_helper(5)  # retry
                except socket_error as s:
                    # https://stackoverflow.com/questions/14425401/catch-socket-error-errno-111-connection-refused-exception
                    # if we get a connection refused in browser.page_source
                    if s.errno != errno.ECONNREFUSED:
                        raise s  # re-raise if it isn't connection refused
                    else:  # if it is, try again in 5 seconds
                        _safe_browser_close(browser)
                        _sleep_retry_print_helper(5)  # retry
        display.stop()
    if text is None:
        raise ValueError("couldn't get html text from url:"+url)
    return text
