"""
Scrapper of localized strings from jw org
"""

import HTMLParser
from resources.lib.constants import ScrappedStringID as T


class JwOrgParser(HTMLParser.HTMLParser):
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
        HTMLParser.HTMLParser.__init__(self)

        self.depth = 0
        self.save_options = 0  # depth
        self.save_data = 0  # depth
        self.data_name = None
        self.strings = {}  # name, translation

    @classmethod
    def parse(cls, data):
        # type: (str) -> dict
        """Takes HTML data as input and returns a dictionary with translations"""

        p = cls()
        p.feed(data)
        return p.strings

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
                self.save_data = self.depth
                self.data_name = T.BIBLE
            elif 'PublicationsMagazinesLandingPage' in classes:
                self.save_data = self.depth
                self.data_name = T.MAGAZINES
            elif 'PublicationsDefaultLandingPage' in classes:
                self.save_data = self.depth
                self.data_name = T.BOOKS

        elif tag == 'select':
            if 'jsPublicationFilter' in classes:
                self.save_options = self.depth

        elif tag == 'option':
            if self.save_options:
                pub = next((str(a[1]) for a in attrs if a[0] == 'value'), '')
                if pub in ('g', 'w', 'wp', 'ws'):
                    self.save_data = self.depth
                    self.data_name = pub

    def handle_data(self, data):
        """
        :param data: Some kind of string, blanks and newline will be stripped, empty strings ignored
        """
        # If we are inside a matching tag, save the data (only first time)
        if self.save_data:
            data = data.strip()
            if data and self.data_name not in self.strings:
                self.strings[self.data_name] = data

    def handle_endtag(self, tag):
        self.depth -= 1

        # If we go a level ABOVE a matching tag, forget about it
        if self.depth < self.save_data:
            self.save_data = 0
            self.data_name = None

        if self.depth < self.save_options:
            self.save_options = 0
