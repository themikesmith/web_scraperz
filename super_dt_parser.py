__author__ = 'mcs'
from dateutil import parser as dt_parser
from dateutil.tz import tzoffset
from datetime import datetime

def safe_dt_parse(dt):
    d = dt_parser.parse(dt)
    try:
        print d
    except ValueError:  # throws this weird tz bug
        # https://bugs.python.org/issue13556
        d = datetime(year=d.year, month=d.month, day=d.day, hour=d.hour, minute=d.minute, second=d.second,
                     microsecond=d.microsecond, tzinfo=tzoffset(None, 0))
    return d
