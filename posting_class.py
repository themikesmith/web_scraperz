from fuzzywuzzy import fuzz
from collections import MutableMapping
from sys import stderr
__author__ = 'mcs'


class Posting(MutableMapping):
    """
    This class represents a "posting", storing data, and testing equality
     based on fuzzy matching to text content.

    In the __eq__ and __hash__ methods, currently checks for description first
     THEN moves to ID / source pair.  Edit if you want.
     Only fuzzy matches the description -- figured ID / source pair was bad to fuzzy match =)
    """
    DESCRIPTION = "description"
    SOURCE = "source"
    ID = "unique_id"
    TITLE = "title"
    DATE_POSTED = "date_posted"
    URL = "url"
    FUZZY_THRESHOLD = 90

    def __init__(self, *args, **kwargs):
        self.data = dict()
        self.update(dict(*args, **kwargs))
        self.use_fuzzy = True

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __delitem__(self, key):
        del self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def __contains__(self, item):
        return dict.__contains__(self.data, item)

    def __repr__(self):
        dict_repr = dict.__repr__(self.data)
        return '%s(%s)' % (type(self).__name__, dict_repr)

    def __str__(self):
        return dict.__str__(self.data)

    def __hash__(self):
        if Posting.DESCRIPTION in self and Posting.SOURCE in self:
            s = self[Posting.DESCRIPTION] + self[Posting.SOURCE]
            return s.__hash__()
        elif Posting.ID in self and Posting.SOURCE in self:
            s = self[Posting.ID] + self[Posting.SOURCE]
            return s.__hash__()
        else:
            raise ValueError("Error when hashing: posting doesn't have description and source"
                             ", nor id + source\n%s" % self)

    def __eq__(self, other):
        if Posting.DESCRIPTION in self and Posting.DESCRIPTION in other \
                and Posting.SOURCE in self and Posting.SOURCE in other:
            if self.use_fuzzy:
                result = fuzz.ratio(self[Posting.DESCRIPTION], other[Posting.DESCRIPTION]) >= Posting.FUZZY_THRESHOLD
                return result and self[Posting.SOURCE].__hash__() == other[Posting.SOURCE].__hash__()
            else:  # calling hash in this instance will default to using description and source
                return self.__hash__() == other.__hash__()
        elif Posting.ID in self and Posting.SOURCE in self and Posting.ID in other and Posting.SOURCE in other:
            s = self[Posting.ID] + self[Posting.SOURCE]
            o = other[Posting.ID] + other[Posting.SOURCE]
            # can't call hash on the objects in this instance because one could have a description
            return s.__hash__() == o.__hash__()
        else:
            raise ValueError("Error in __eq__: posting doesn't have description and source,"
                             " nor id + source\nself:%s\nother:%s" % (self, other))

    def __ne__(self, other):
        return not self.__eq__(other)

    def add_data(self, key, value):
        self[key] = value

    def add_id(self, value):
        self[Posting.ID] = value

    def add_url(self, value):
        self[Posting.URL] = value

    def add_title(self, value):
        self[Posting.TITLE] = value

    def add_source(self, value):
        self[Posting.SOURCE] = value

    def add_description(self, value):
        self[Posting.DESCRIPTION] = value

    def add_date_posted(self, value):
        self[Posting.DATE_POSTED] = value

    def get_data_backing(self):
        return self.__dict__


if __name__ == "__main__":
    blank = Posting()
    blank_two = Posting()
    partial_id = Posting()
    partial_id.add_id("12")
    partial_source = Posting()
    partial_source.add_source("craigslist")
    partial_id_source = Posting()
    partial_id_source.add_id("11")
    partial_id_source.add_source("craigslist")
    partial_id_source_two = Posting()
    partial_id_source_two.add_id("11")
    partial_id_source_two.add_source("craigslist")
    partial_description = Posting()
    partial_description.add_description("This is a test description")
    full_match = Posting()
    full_match.add_description("This is a test description")
    full_match.add_id("11")
    full_match.add_source("craigslist")
    full_nomatch = Posting()
    full_nomatch.add_description("This is a stupid description")
    full_nomatch[Posting.ID] = "11"
    full_nomatch.add_source("craigslist")
    full_match_fuzzy = Posting()
    full_match_fuzzy.add_description("This is a super test description")
    full_match_fuzzy.add_id("11")
    full_match_fuzzy.add_source("craigslist")
    full_match_notsource = Posting()
    full_match_notsource.add_description("This is a test description")
    full_match_notsource.add_id("11")
    full_match_notsource.add_source("indeed")
    d = {Posting.ID: "123"}
    add_dict = Posting(d)
    assert str(add_dict) == str(d)

    try:
        blank == blank_two
        assert False
    except ValueError:
        assert True
    try:
        blank == full_match
        assert False
    except ValueError:
        assert True
    try:
        partial_id == full_match
        assert False
    except ValueError:
        assert True
    try:
        partial_source == full_match
        assert False
    except ValueError:
        assert True
    try:
        assert partial_description != full_match
        assert False
    except ValueError:
        assert True
    try:
        assert partial_id_source == full_match
    except ValueError:
        assert False
    try:
        assert full_nomatch != full_match
    except ValueError:
        assert False
    try:
        assert full_match_fuzzy == full_match
    except ValueError:
        assert False
    assert full_match != full_match_notsource
