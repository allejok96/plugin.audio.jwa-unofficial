"""
Static names for valid URL queries etc, to simplify for the IDE (and me)
and some craziness to be able to write more beautiful code
"""
from __future__ import absolute_import, division, unicode_literals

ICON_BIBLE = 'https://wol.jw.org/img/bibles@3x.png'
ICON_BOOKS = 'https://wol.jw.org/img/books@3x.png'
ICON_WATCHTOWER = 'https://wol.jw.org/img/watchtower@3x.png'
ICON_AWAKE = 'https://wol.jw.org/img/awake@3x.png'

LANGUAGE_API = 'https://www.jw.org/en/languages'
PUBMEDIA_API = 'https://pubmedia.jw-api.org/GETPUBMEDIALINKS'
FINDER_API = 'https://www.jw.org/finder'
DOCID_MAGAZINES = '1011209'  # corresponds to the magazines page (2020-04-18)


class AttributeProxy(object):
    """Run a function when getting attributes

    For example:
        p = AttributeProxy(function)
        p.x

    Will be the same as calling:
        function(AttributeProxy.x)
    """

    def __init__(self, function):
        self._func = function

    def __getattribute__(self, name):
        # Py2: getattribute is ok with unicode, as long as it's all ASCII characters
        custom_function = super(AttributeProxy, self).__getattribute__('_func')
        original_value = super(AttributeProxy, self).__getattribute__(name)
        return custom_function(original_value)


class Query(object):
    """Strings for URL queries to addon itself"""
    MODE = 'mode'
    YEAR = 'year'
    LANG = 'lang'
    LANG_NAME = 'langname'
    PUB = 'pub'
    ISSUE = 'issue'
    BOOKNUM = 'booknum'
    TRACK = 'track'


class Mode(object):
    """Modes for use with mode= query to addon itself"""
    OPEN = 'open'
    BIBLE = 'bible'
    MAGAZINES = 'mag'
    BOOKS = 'books'
    ADD_BOOKS = 'bookadd'
    LANGUAGES = 'langlist'
    SET_LANG = 'setlang'
    CLEAN_CACHE = 'clean'


class SettingID(object):
    """Setting IDs in Kodi"""
    LANG = 'language'
    LANG_HIST = 'langhist'
    LANG_NAME = 'langname'
    STARTUP_MSG = 'startupmsg'
    SCRAPPER = 'trscrapper'


class ScrappedStringID(AttributeProxy):
    """IDs for the translation database"""
    BIBLE = 'bible'
    MAGAZINES = 'magazines'
    BOOKS = 'books'
    # These values derived from jw.org and cannot be changed
    # They are only here to keep things consistent
    AWAKE = 'g'
    WT = 'wp'
    WT_STUDY = 'w'
    WT_SIMPLE = 'ws'


class LocalizedStringID(AttributeProxy):
    """IDs for strings from PO file"""
    # Auto generated, by running this module directly
    PLAY_LANG = 30003
    CONNECTION_ERROR = 30004
    LOADING_LANG = 30005
    THEO_WARN = 30006
    NOT_SUPP_JW = 30007
    UNDERSTAND = 30008
    MORE_INFO = 30009
    BIBLE = 30010
    MAGAZINES = 30011
    BOOKS = 30012
    NOT_AVAIL = 30013
    ADD_MORE = 30014
    AUTO_SCAN = 30015
    SCAN_QUESTION = 30016
    SCANNING = 30017
    SCAN_DONE = 30018
    ENTER_PUB = 30019
    PUB_ADDED = 30020
    WRONG_CODE = 30021
    CLEAN_CACHE = 30022
    CLEAN_QUESTION = 30023
    CACHE_CLEANED = 30024
    TRANS_UPDATE = 30025
    DISCLAIMER = 30026
    DB_ERROR = 30027
    WT = 30031
    WT_STUDY = 30032
    WT_SIMPLE = 30033
    AWAKE = 30034


def _generate_string_ids():
    # Py2: 'rb' gives us bytes in both Py2 and Py3 so we can decode it to unicode
    strings = open('../language/resource.language.en_gb/strings.po', 'rb').read().decode('utf-8')
    comment = None
    for line in strings.split('\n'):
        if line.startswith('# '):
            comment = line[2:].replace(' ', '_').upper()
        elif line.startswith('msgctxt') and comment:
            print('{} = {}'.format(comment, line[10:15]))
            comment = None


if __name__ == '__main__':
    _generate_string_ids()
