"""
Scrapper of localized strings from jw org
"""
from __future__ import absolute_import, division, unicode_literals

from resources.lib.constants import ScrappedStringID as T

try:
    from html.parser import HTMLParser, unescape
except ImportError:
    from HTMLParser import HTMLParser

    # Py2: accepts both unicode and byte string, always returns unicode
    unescape = HTMLParser().unescape
    str = unicode


class JwOrgParser(HTMLParser):
    """
    The parser is adapted to https://www.jw.org/en/library/magazines/ (or corresponding page)

    Call it using the class method parse()

    It will grab the main menu item names from the navigation menu at the top of the page,
    and the names of the magazines from the drop down list in the "display filter".

    This is the basic HTML code that the parser will look for (only the first occurrence of each string will be saved):

    <div class="BibleLandingPage" role="listitem">BIBLE TRANSLATION</div>
    <div class="PublicationsMagazinesLandingPage" role="listitem">MAGAZINES TRANSLATION</div>
    <div class="PublicationsDefaultLandingPage" role="listitem">BOOKS TRANSLATION</div>
    <select class="jsPublicationFilter">
        <option value="PUBLICATION CODE">NAME OF PUBLICATION</option>
    </select>
    """

    def __init__(self):
        # Cannot use super since Py2 HTMLParser is an old style class
        HTMLParser.__init__(self)

        self.depth = 0
        self.look_for_options = 0  # depth
        self.look_for_data = 0  # depth
        self.temp = ''  # concatenation of data
        self.data_name = None  # dict key
        self.strings = {}  # key, string

    @classmethod
    def parse(cls, data):
        # type: (str) -> dict
        """Takes HTML data as input and returns a dictionary with translations"""

        parser = cls()
        # Remove indentation
        for line in data.splitlines():
            line = line.strip()
            if line:
                parser.feed(line + '\n')
        return parser.strings

    def _gather_data(self, name):
        self.look_for_data = self.depth
        self.data_name = name
        self.temp = ''

    def handle_starttag(self, tag, attrs):
        """
        :param tag: Name of the HTML tag
        :param attrs: List[Tuple[key, value], ...]
        """
        # Keep track of how many tags we are inside
        self.depth += 1

        classes = next((a[1] for a in attrs if a[0] == 'class'), '').split()
        role = next((a[1] for a in attrs if a[0] == 'role'), '')

        # For matching tags: Save level and type of tag to save the contained data later

        if tag == 'div' and role == 'listitem':
            if 'BibleLandingPage' in classes:
                self._gather_data(T.BIBLE)
            elif 'PublicationsMagazinesLandingPage' in classes:
                self._gather_data(T.MAGAZINES)
            elif 'PublicationsDefaultLandingPage' in classes:
                self._gather_data(T.BOOKS)

        elif tag == 'select':
            if 'jsPublicationFilter' in classes:
                self.look_for_options = self.depth

        elif tag == 'option':
            if self.look_for_options:
                pub = next((str(a[1]) for a in attrs if a[0] == 'value'), '')
                if pub in ('g', 'w', 'wp', 'ws'):
                    self._gather_data(pub)

    def handle_data(self, data):
        """
        :param data: Some kind of string, blanks and newline will be stripped, empty strings ignored
        """
        # If we are inside a matching tag, save the data (only data inside this tag)
        if self.look_for_data:
            self.temp += data

    def handle_entityref(self, name):
        if self.look_for_data:
            self.temp += unescape('&' + name + ';')

    handle_charref = handle_entityref

    def handle_endtag(self, tag):
        self.depth -= 1

        # If we go a level ABOVE a matching tag
        if self.depth < self.look_for_data:
            # Save stored data, the first time
            if self.look_for_data and self.data_name not in self.strings:
                self.strings[self.data_name] = self.temp.replace('\n', '')
            # Forget about it
            self.look_for_data = 0
            self.data_name = None

        if self.depth < self.look_for_options:
            self.look_for_options = 0
