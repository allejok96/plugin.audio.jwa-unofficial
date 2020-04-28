#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
import sys
import traceback
from datetime import datetime, date, timedelta
from kodi_six import xbmc, xbmcaddon, xbmcgui, xbmcplugin, py2_encode, py2_decode
from sqlite3 import Error as DBError

from resources.lib.constants import *
from resources.lib.database import CacheDatabase, PublicationData, MediaData, TranslationData, Ignore
from resources.lib.scrapper import JwOrgParser, unescape

Q = Query
M = Mode

try:
    from urllib.error import HTTPError
    from urllib.parse import parse_qs, urlencode
    from urllib.request import urlopen

except ImportError:
    from urllib2 import HTTPError, urlopen
    from urlparse import parse_qs as _parse_qs
    from urllib import urlencode as _urlencode

    # Py2: urlencode only accepts byte strings
    def urlencode(query):
        # Dict[str, str] -> str
        return py2_decode(_urlencode({py2_encode(param): py2_encode(arg) for param, arg in query.items()}))

    # Py2: even if parse_qs accepts unicode, the return makes no sense
    def parse_qs(qs):
        # str -> Dict[str, List[str]]
        return {py2_decode(param): [py2_decode(a) for a in args]
                for param, args in _parse_qs(py2_encode(qs)).items()}

    # Py2: When using str, we mean unicode string
    str = unicode


class NotFoundError(Exception):
    """Raised when getting a 404"""
    pass


def log(msg, level=xbmc.LOGDEBUG):
    """Write to log file"""

    for line in msg.splitlines():
        xbmc.log(addon.getAddonInfo('id') + ': ' + line, level)


def notification(msg, **kwargs):
    """Show a GUI notification"""

    # Py2: dict.get() is ok with unicode, as long as it's all ASCII characters
    xbmcgui.Dialog().notification(addon.getAddonInfo('name'), msg,
                                  icon=kwargs.get('icon') or xbmcgui.NOTIFICATION_ERROR)


def get_json(url, exit_on_404=True):
    # type: (str, bool) -> dict
    """Fetch JSON data from an URL and return it as a dict"""

    log('opening ' + url, xbmc.LOGINFO)
    try:
        # urlopen returns bytes
        # Set high timeout, because AWS blocks requests from urllib for about 10 sec
        data = urlopen(url, timeout=20).read().decode('utf-8')

    # Catches URLError, HTTPError, SSLError ...
    except IOError as e:
        # Pass on 404 for handling by someone else
        if isinstance(e, HTTPError) and e.code == 404 and not exit_on_404:
            raise NotFoundError
        log(traceback.format_exc(), level=xbmc.LOGERROR)
        notification(S.CONNECTION_ERROR)
        exit(1)
        raise  # to make PyCharm happy

    return json.loads(data)


def getpubmedialinks_json(pubdata, alllangs=False, exit_on_404=True):
    """Make a request to JW API and return JSON as a dict"""

    assert pubdata.pub

    query = dict(output='json',
                 fileformat='MP3',
                 pub=pubdata.pub,
                 issue=pubdata.issue,
                 booknum=pubdata.booknum,
                 langspoken=pubdata.lang,
                 txtCMSLang=pubdata.lang,
                 alllangs=int(alllangs))
    # Remove empty queries
    query = {key: value for key, value in query.items() if value is not None}
    return get_json(PUBMEDIA_API + '?' + urlencode(query), exit_on_404=exit_on_404)


def request_to_self(pubdata=None, mode=None, pub=None, year=None, lang=None, langname=None, track=None):
    # type: (PublicationData, str, str, int, str, str, int) -> str
    """Return a string with an URL request to the add-on itself

    Arguments override values from pubdata.

    :param pubdata: Grab info from this object
    :param mode: Should be one of the M constants
    :param pub: Publication code
    :param year: Year (for magazines)
    :param lang: Language code
    :param langname: Language name (visible in settings)
    :param track: Track number (for direct playback)
    """

    query = {Q.MODE: mode,
             Q.PUB: pub,
             Q.LANG: lang,
             Q.LANG_NAME: langname,
             Q.YEAR: year,
             Q.TRACK: track}

    # Overwrite empty values with values from pubdata
    if pubdata:
        query.update({
            Q.PUB: pub or pubdata.pub,
            Q.ISSUE: pubdata.issue,
            Q.BOOKNUM: pubdata.booknum,
            Q.LANG: lang or pubdata.lang})

    # Remove empty queries
    query = {key: value for key, value in query.items() if value is not None}

    # argv[0] is path to the plugin
    return sys.argv[0] + '?' + urlencode(query)


def get_translation(key):
    """Quick way to get a translated string from the cache"""

    try:
        search = TranslationData(key=key, lang=global_language)
        result = next(cache.trans.select(search))
        return result.string
    except StopIteration:
        return None


def update_translations(lang):
    """Download a jw.org web page and save some extracted strings to cache"""

    # If there are any translations for the current language in the cache, do nothing
    if any(cache.trans.select(TranslationData(lang=lang))):
        return

    progressbar = xbmcgui.DialogProgress()
    progressbar.create('', S.TRANS_UPDATE)
    progressbar.update(50)
    try:
        url = '{}?docid={}&wtlocale={}'.format(FINDER_API, DOCID_MAGAZINES, lang)
        # urlopen returns bytes
        response = urlopen(url).read().decode('utf-8')
        translations = JwOrgParser.parse(response)
        for key, value in translations.items():
            cache.trans.delete(TranslationData(key=key, lang=lang))
            cache.trans.insert(TranslationData(key=key, string=value, lang=lang))
    finally:
        progressbar.close()


def download_pub_data(pubdata):
    # type: (PublicationData) -> ()
    """Download and cache publication metadata

    Return publication and list of contained media
    """
    try:
        j = getpubmedialinks_json(pubdata, exit_on_404=False)

    except NotFoundError:
        # Cache the failure... yes, that's right, so we don't retry for a while
        cache.publ.delete(pubdata)
        failed_pub = PublicationData.copy(pubdata)
        failed_pub.failed = datetime.now()
        cache.publ.insert(failed_pub)
        raise

    # Remove old publication metadata
    # For bible index page: remove all bible books
    if pubdata.booknum == 0:
        bible = PublicationData.copy(pubdata)
        bible.booknum = Ignore
        cache.publ.delete(bible)
    else:
        cache.publ.delete(pubdata)

    # Store new publication metadata
    # Note: opening a publication for browsing media will refresh it
    # and the Bible index page will refresh each time it opens too
    # so we don't have to worry about entries growing old
    new_pub = PublicationData.copy(pubdata)
    title = j['pubName']
    if j.get('formattedDate'):
        title += ' ' + j['formattedDate']
    new_pub.title = unescape(title)
    new_pub.icon = j.get('pubImage', {}).get('url')
    cache.publ.insert(new_pub)

    media_list = []
    try:
        for j_file in j['files'][pubdata.lang]['MP3']:
            try:
                # Store new media metadata
                if j_file.get('mimetype') == 'audio/mpeg':
                    m = MediaData.copy(pubdata)
                    m.url = j_file['file']['url']
                    m.title = unescape(j_file['title'])
                    m.duration = j_file.get('duration')
                    m.track = int(j_file.get('track'))
                    media_list.append(m)

                # For the bible index page: Store title metadata in the publications table
                elif pubdata.booknum == 0:
                    sub_pub = PublicationData.copy(pubdata)
                    sub_pub.title = unescape(j_file['title'])
                    sub_pub.booknum = int(j_file['booknum'])
                    cache.publ.insert(sub_pub)

            except KeyError:
                pass

    except KeyError:
        pass

    return new_pub, media_list


def get_pub_data(pubdata):
    # type: (PublicationData) -> ()
    """Get publication metadata from cache (download if needed)"""

    # Check for previous records
    cached_pub = next(cache.publ.select(pubdata), None)
    # No record
    if cached_pub is None:
        pass
    # Up to date
    elif cached_pub.failed is None:
        return cached_pub
    # Has failed within the last 24 hours
    elif datetime.now() < cached_pub.failed + timedelta(days=1):
        raise NotFoundError
    # Refresh
    pub, media = download_pub_data(pubdata)
    return pub


class MenuItem(object):
    """A general menu item (folder)"""

    is_folder = True

    def __init__(self, url, title, icon=None, fanart=None):
        self.url = url
        self.title = title
        self.icon = icon
        self.fanart = fanart

    def listitem(self):
        """Create a Kodi listitem from the metadata"""

        try:
            # offscreen is a Kodi v18 feature
            # We wont't be able to change the listitem after running .addDirectoryItem()
            # But load time for this function is cut down by 93% (!)
            li = xbmcgui.ListItem(self.title, offscreen=True)
        except TypeError:
            li = xbmcgui.ListItem(self.title)

        # setArt can be kinda slow, so don't run if it's empty
        if self.icon or self.fanart:
            li.setArt(dict(icon=self.icon, poster=self.icon, fanart=self.fanart))

        return li

    def add_item_in_kodi(self, total=0):
        """Adds this as a directory item in Kodi"""

        # totalItems doesn't seem to have any effect in Estuary skin, but let's keep it anyway
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=self.url, listitem=self.listitem(),
                                    isFolder=self.is_folder, totalItems=total)


class PublicationItem(MenuItem):
    """A folder that represents a publication

    At the moment, it's virtually identical to a MenuItem
    """

    def __init__(self, pubdata):
        # type: (PublicationData) -> None

        super(PublicationItem, self).__init__(url=request_to_self(pubdata, mode=M.OPEN),
                                              title=pubdata.title,
                                              icon=pubdata.icon)


class MediaItem(MenuItem):
    """A playable article (audio file)"""

    is_folder = False

    def __init__(self, mediadata):
        # type: (MediaData) -> None

        super(MediaItem, self).__init__(mediadata.url, mediadata.title)
        self.duration = mediadata.duration

        # Parent publication and track are needed for Play in other language
        self.pubdata = PublicationData.copy(mediadata)
        self.track = mediadata.track

    def listitem(self):
        li = super(MediaItem, self).listitem()

        li.setInfo('music', dict(duration=self.duration, title=self.title))

        # Other language action
        # Note: RunPlugin opens as a background process
        action = 'RunPlugin(' + request_to_self(self.pubdata, mode=M.LANGUAGES, track=self.track) + ')'
        li.addContextMenuItems([(S.PLAY_LANG, action)])

        return li


def top_level_page():
    """The main menu"""

    if addon.getSetting(SettingID.STARTUP_MSG) == 'true':
        dialog = xbmcgui.Dialog()
        if dialog.yesno(S.THEO_WARN, S.NOT_SUPP_JW, nolabel=S.UNDERSTAND, yeslabel=S.MORE_INFO):
            dialog.textviewer(S.THEO_WARN, S.DISCLAIMER)

    # Auto set language, if it has never been set and Kodi is configured for something else then English
    isolang = xbmc.getLanguage(xbmc.ISO_639_1)
    if not addon.getSetting(SettingID.LANG_HIST) and isolang != 'en':
        try:
            # Search for matching language, save setting (and update translations)
            language_dialog(preselect=isolang)
            # Reload for this instance
            global global_language
            global_language = addon.getSetting(SettingID.LANG) or 'E'
        except StopIteration:
            # No suitable language was found, just write something to history, so this check won't run again
            addon.setSetting(SettingID.LANG_HIST, 'E')

    MenuItem(request_to_self(mode=M.BIBLE),
             T.BIBLE or S.BIBLE,
             icon=ICON_BIBLE).add_item_in_kodi()
    MenuItem(request_to_self(mode=M.MAGAZINES),
             T.MAGAZINES or S.MAGAZINES,
             icon=ICON_WATCHTOWER).add_item_in_kodi()
    MenuItem(request_to_self(mode=M.BOOKS),
             T.BOOKS or S.BOOKS,
             icon=ICON_BOOKS).add_item_in_kodi()
    xbmcplugin.endOfDirectory(addon_handle)


def bible_page():
    """Bible menu"""

    success = False
    for bible in 'bi12', 'nwt':
        try:
            request = PublicationData(pub=bible, booknum=0, lang=global_language)
            # Note: we download the bible index page, so it's always current
            pub, media = download_pub_data(request)
            # Remove that ugly icon from bi-12
            pub.icon = None
            PublicationItem(pub).add_item_in_kodi()
            success = True
        except NotFoundError:
            pass

    if not success:
        xbmcgui.Dialog().ok('', S.NOT_AVAIL)
        # Note: return will prevent Kodi from creating an empty folder view
        return

    xbmcplugin.endOfDirectory(addon_handle)


def magazine_page(pub=None, year=None):
    # type: (str, int) -> None
    """Browse magazines

    With no arguments, display a list of magazines.

    :param pub: Display a list of years for this magazine.
    :param year: Display a list of issues from this year.
    """
    # Magazine list
    if not pub:
        MenuItem(request_to_self(mode=M.MAGAZINES, pub='g'),
                 T.AWAKE or S.AWAKE,
                 icon=ICON_AWAKE).add_item_in_kodi()

        MenuItem(request_to_self(mode=M.MAGAZINES, pub='wp'),
                 T.WT or S.WT,
                 icon=ICON_WATCHTOWER).add_item_in_kodi()

        MenuItem(request_to_self(mode=M.MAGAZINES, pub='w'),
                 T.WT_STUDY or S.WT_STUDY,
                 icon=ICON_WATCHTOWER).add_item_in_kodi()

        # Simplified only existed in a few languages
        if global_language in ('E', 'F', 'I', 'T', 'S'):
            MenuItem(request_to_self(mode=M.MAGAZINES, pub='ws'),
                     T.WT_SIMPLE or S.WT_SIMPLE,
                     icon=ICON_WATCHTOWER).add_item_in_kodi()

    # Year list
    elif not year:
        # 2008 was the first year of recordings in English
        # Other languages are different, but we'll just have to try and fail
        max_year = date.today().year + 1
        ranges = {'w': range(2008, max_year),
                  'wp': range(2008, max_year),
                  'ws': range(2013, 2018),  # first english: 2013-08-15, last 2018-12
                  'g': range(2008, max_year)}

        for year in sorted(ranges[pub], reverse=True):
            MenuItem(request_to_self(mode=M.MAGAZINES, pub=pub, year=year), str(year)).add_item_in_kodi()

    # Issue list
    else:
        # Determine release dates
        if year == date.today().year:
            max_month = date.today().month + 1
            ranges = {'w': range(1, max_month),
                      'wp': range(1, 4, max_month),
                      'g': range(3, 4, max_month)}
            issues = ['{}{:02}'.format(year, month) for month in ranges[pub]]
        elif year >= 2018:
            ranges = {'w': range(1, 13),
                      'wp': (1, 5, 9),
                      'g': (3, 7, 11)}
            issues = ['{}{:02}'.format(year, month) for month in ranges[pub]]
        elif year >= 2016:
            ranges = {'w': range(1, 13),
                      'ws': range(1, 13),
                      'wp': range(1, 13, 2),  # odd months
                      'g': range(2, 13, 2)}  # even months
            issues = ['{}{:02}'.format(year, month) for month in ranges[pub]]
        else:
            days = {'wp': '01',
                    'w': '15',
                    'ws': '15',
                    'g': ''}
            issues = ['{}{:02}{}'.format(year, month, days[pub]) for month in range(1, 13)]

        success = False
        for issue in issues:
            try:
                request = PublicationData(pub, issue=issue, lang=global_language)
                get_pub_data(request)
                PublicationItem(next(cache.publ.select(request))).add_item_in_kodi(total=len(issues))
                success = True
            except NotFoundError:
                pass

        if not success:
            xbmcgui.Dialog().ok('', S.NOT_AVAIL)
            # Note: return will prevent Kodi from creating an empty folder view
            return

    xbmcplugin.endOfDirectory(addon_handle)


def pub_content_page(pubdata):
    # type: (PublicationData) -> None
    """Browse any publication"""

    if pubdata.booknum == 0:
        # Refresh if necessary (like if we've opened in another language)
        get_pub_data(pubdata)
        # Get all bible books in the bible
        search = PublicationData.copy(pubdata)
        search.booknum = Ignore
        items = [PublicationItem(result)
                 for result in sorted(cache.publ.select(search), key=lambda x: x.booknum)
                 if result.booknum is not None and result.booknum != 0]
    else:
        xbmcplugin.setContent(addon_handle, 'songs')
        pub, media_list = download_pub_data(pubdata)
        items = [MediaItem(m) for m in sorted(media_list, key=lambda x: x.track)]

    for item in items:
        item.add_item_in_kodi()
    xbmcplugin.endOfDirectory(addon_handle)


def books_page():
    """Display all cached books"""

    items = [PublicationItem(result)
             for result in cache.publ.select(PublicationData(lang=global_language))
             if result.pub not in ('g', 'w', 'wp', 'ws', 'nwt', 'bi12')
             if result.failed is None]

    for b in sorted(items, key=lambda x: x.title):
        b.add_item_in_kodi()

    MenuItem(request_to_self(mode=M.ADD_BOOKS), S.ADD_MORE).add_item_in_kodi()

    xbmcplugin.endOfDirectory(addon_handle)


def add_books_dialog(auto=False):
    """Try to add a bunch of publications, or enter one manually"""

    books = 'bh bhs bt cf cl fg fy gt hf hl ia jd jl jr jy kr la lc lfb ll lr lv lvs mb my rj rr th yb10 yb11 ' \
            'yb12 yb13 yb14 yb15 yb16 yb17 yc ypq'.split()

    if auto or xbmcgui.Dialog().yesno(S.AUTO_SCAN, S.SCAN_QUESTION):
        progressbar = xbmcgui.DialogProgress()
        progressbar.create(S.AUTO_SCAN)
        try:
            for i in range(len(books)):
                if progressbar.iscanceled():
                    break
                progressbar.update(i * 100 // len(books), S.SCANNING + ' ' + books[i])
                try:
                    get_pub_data(PublicationData(pub=books[i], lang=global_language))
                except NotFoundError:
                    pass
            else:
                xbmcgui.Dialog().ok(S.AUTO_SCAN, S.SCAN_DONE)
        finally:
            progressbar.close()

    else:
        code = xbmcgui.Dialog().input(S.ENTER_PUB)
        if code:
            try:
                get_pub_data(PublicationData(pub=code, lang=global_language))
                xbmcgui.Dialog().ok('', S.PUB_ADDED)
            except NotFoundError:
                xbmcgui.Dialog().ok('', S.WRONG_CODE)


def language_dialog(pubdata=None, track=None, preselect=None):
    # type: (PublicationData, int, str) -> None
    """Show a dialog window with languages

    :param pubdata: Search available language for this publication, instead of globally (needs track)
    :param track: Dialog will play this track instead of setting language (needs pubdata)
    :param preselect: ISO language code to search for and set as global language
    """
    progressbar = xbmcgui.DialogProgress()
    progressbar.create('', S.LOADING_LANG)
    progressbar.update(1)

    try:
        # Get language data in the form of (lang, name)
        if pubdata:
            data = getpubmedialinks_json(pubdata, alllangs=True)
            # Note: data['languages'] is a dict
            languages = [(code, data['languages'][code]['name']) for code in data['languages']]
            # Sort by name (list is provided sorted by code)
            languages.sort(key=lambda x: x[1])
        else:
            # Note: the list from jw.org is already sorted by ['name']
            data = get_json(LANGUAGE_API)
            if preselect:
                for l in data['languages']:
                    if l.get('symbol') == preselect:
                        log('autoselecting language: {}'.format(l['langcode']))
                        set_language_action(l['langcode'], l['name'] + ' / ' + l['vernacularName'])
                        return
                else:
                    raise StopIteration
            else:
                # Note: data['languages'] is a list
                languages = [(l['langcode'], l['name'] + ' / ' + l['vernacularName'])
                             for l in data['languages']]

        # Get the languages matching the ones from history and put them first
        history = addon.getSetting(SettingID.LANG_HIST).split()
        languages = [l for l in languages if l[0] in history] + languages

        dialog_strings = []
        dialog_actions = []
        for code, name in languages:
            dialog_strings.append(name)
            if pubdata:
                request = request_to_self(pubdata, mode=M.OPEN, lang=code, track=track)
            else:
                request = request_to_self(mode=M.SET_LANG, lang=code, langname=name)
            # Note: RunPlugin opens in the background
            dialog_actions.append('RunPlugin(' + request + ')')

    finally:
        progressbar.close()

    selection = xbmcgui.Dialog().select('', dialog_strings)
    if selection >= 0:
        xbmc.executebuiltin(dialog_actions[selection])


def set_language_action(lang, printable_name=None):
    """Save a language setting"""

    addon.setSetting(SettingID.LANG, lang)
    addon.setSetting(SettingID.LANG_NAME, printable_name or lang)
    save_language_history(lang)

    if lang != 'E' and enable_scrapper:
        update_translations(lang)


def save_language_history(lang):
    """Save a language code first in history"""

    history = addon.getSetting(SettingID.LANG_HIST).split()
    history = [lang] + [h for h in history if h != lang]
    history = history[0:5]
    addon.setSetting(SettingID.LANG_HIST, ' '.join(history))


def play_track(pubdata, track):
    # type: (PublicationData, int) -> None
    """Start playback of a track in a publication"""

    try:
        pub, media_list = download_pub_data(pubdata)
        item = next(MediaItem(m) for m in media_list if m.track == track)
        xbmc.Player().play(item.url, item.listitem())
    except (NotFoundError, StopIteration):
        xbmcgui.Dialog().ok('', S.NOT_AVAIL)


addon_handle = int(sys.argv[1])  # needed for gui
addon = xbmcaddon.Addon()  # needed for info
global_language = addon.getSetting(SettingID.LANG) or 'E'
enable_scrapper = addon.getSetting(SettingID.SCRAPPER) == 'true'

addon_dir = xbmc.translatePath(addon.getAddonInfo('profile'))
try:
    os.makedirs(addon_dir)  # needed first run
except OSError:
    pass
cache_path = os.path.join(addon_dir, 'cache.db')

# Special class that will lookup its values in Kodi's language file
S = LocalizedStringID(addon.getLocalizedString)

# Tested in Kodi 18: disables all viewtypes except list, and there will be no icons in the list
xbmcplugin.setContent(addon_handle, 'files')

# The awkward way Kodi passes arguments to the add-on...
# argv[2] is a URL query string, probably passed by request_to_self()
# example: ?mode=play&media=ThisVideo
args = parse_qs(sys.argv[2][1:])
# parse_qs puts the values in a list, so we grab the first value for each key
args = {k: v[0] for k, v in args.items()}

arg_mode = args.get(Q.MODE)

# Do this before connecting to database
if arg_mode == M.CLEAN_CACHE:
    if xbmcgui.Dialog().yesno(S.CLEAN_CACHE, S.CLEAN_QUESTION):
        if os.path.exists(cache_path):
            os.remove(cache_path)
        xbmcgui.Dialog().ok(S.CLEAN_CACHE, S.CACHE_CLEANED)

try:
    log('cache database: ' + cache_path)
    cache = CacheDatabase(cache_path)

    # Special class that will lookup its values in the database of scrapped translations
    if enable_scrapper:
        T = ScrappedStringID(get_translation)
    else:
        # This will return None for all lookups
        T = ScrappedStringID(lambda x: None)

    arg_pub = PublicationData(pub=args.get(Q.PUB),
                              issue=args.get(Q.ISSUE),
                              lang=args.get(Q.LANG) or global_language,
                              booknum=args.get(Q.BOOKNUM) and int(args[Q.BOOKNUM]))

    if arg_mode is None:
        top_level_page()

    elif arg_mode == M.BIBLE:
        bible_page()

    elif arg_mode == M.MAGAZINES:
        magazine_page(pub=args.get(Q.PUB), year=args.get(Q.YEAR) and int(args[Q.YEAR]))

    elif arg_mode == M.BOOKS:
        books_page()

    elif arg_mode == M.ADD_BOOKS:
        add_books_dialog()

    elif arg_mode == M.LANGUAGES:
        if arg_pub.pub:
            language_dialog(pubdata=arg_pub, track=int(args[Q.TRACK]))
        else:
            language_dialog()

    elif arg_mode == M.SET_LANG:
        set_language_action(args[Q.LANG], args.get(Q.LANG_NAME))

    elif arg_mode == M.OPEN:
        # In case we've opened this in another language, save to history
        if arg_pub.lang != global_language:
            save_language_history(arg_pub.lang)

        if Q.TRACK in args:
            play_track(arg_pub, int(args[Q.TRACK]))
        else:
            pub_content_page(arg_pub)

    elif arg_mode == M.CLEAN_CACHE:
        # Since translations was removed with the cache, update them now
        if global_language != 'E' and enable_scrapper:
            update_translations(global_language)

    # Note: no need to close database, due to how sqlite works
    # Only point in closing a connection would be to free memory
    # but this script runs and exits, so there's no point in that

except DBError:
    log('unknown database error', level=xbmc.LOGERROR)
    log(traceback.format_exc(), level=xbmc.LOGERROR)
    notification(S.DB_ERROR)
    exit(1)
