__author__ = 'mcs'
from dateutil import parser as dt_parser
from dateutil.tz import tzoffset
from datetime import datetime, timedelta
from sys import stderr
import re


# two groups - an integer, and the unit of time
_re_time_ago = re.compile(r"(\d+)\+? (year|month|week|day|hour|minute|second|microsecond)s? ago")


def safe_dt_parse(dt):
    """
    Safe wrapper for dt parser, deals with weird TZ bug,
    and also handles 'now', 'today', and X days/months/seconds ago, etc
    :param dt:
    :return:
    """
    s_dt = str(dt)
    # handle 'now'
    if s_dt.lower() == 'now':
        return datetime.now()
    if s_dt.lower() == 'today':
        return datetime.today()
    # handle 'X days/months/seconds ago', etc
    m = _re_time_ago.match(s_dt)
    if m is not None:
        amount = m.group(1)
        unit = m.group(2).lower() + 's'
        time_dict = {unit: float(amount)}
        return datetime.now() - timedelta(**time_dict)
    try:
        d = dt_parser.parse(dt)
    except (AttributeError, ValueError) as e:
        # if dt can't be 'read', or if unknown string format
        raise e
    try:
        print >> stderr, d
    except ValueError:  # if the object can be created but not printed
        # throws this weird tz bug, remove tz info
        # https://bugs.python.org/issue13556
        d = datetime(year=d.year, month=d.month, day=d.day, hour=d.hour, minute=d.minute, second=d.second,
                     microsecond=d.microsecond, tzinfo=tzoffset(None, 0))
    return d
