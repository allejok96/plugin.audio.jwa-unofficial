"""
This module is because SQL is strange
and even tho Python's DB API is cool, it's a mess using it
and I want typing support for everything
"""
from __future__ import absolute_import, division, print_function, unicode_literals

# Py2 note: sqlite.execute() always returns unicode, and seems to prefer unicode input
import sqlite3
from datetime import datetime

# Py2: str will become "unicode" in Py2, and "str" (unicode) in Py3
str = type('')


class Ignore(object):
    """Like None but will be ignored under certain conditions

    Used in DataRow, but it will always be substituted with None before returned
    """
    pass


class DataRow(object):
    """Represents a row of data from a table, with values stored in class attributes."""

    def __getattribute__(self, item):
        """Substitutes Ignore with None on class attribute lookup"""

        value = super(DataRow, self).__getattribute__(item)
        if value is Ignore:
            return None
        return value

    def columns(self):
        """Generator with all column names (names of class attributes)"""

        for key in self.__dict__:
            # Py2: dict key names are byte string, convert them
            yield str(key)

    def values(self):
        """Generator with all values (Ignore becomes None)"""

        for col in self.columns():
            yield getattr(self, col)

    def items(self, include_ignored=False):
        """Return a generator with (column, value)

        :param include_ignored: If False, leave out columns that are set to Ignore
        """
        if include_ignored:
            # Do an attribute lookup, as this will convert Ignore to None
            for col in self.columns():
                yield (col, getattr(self, col))
        else:
            for col in self.__dict__:
                if self.__dict__[col] is not Ignore:
                    # Py2: dict key names are byte string, convert them
                    yield (str(col), getattr(self, col))

    @classmethod
    def copy(cls, obj):
        """Return a new instance, with (matching) attributes copied from another object"""

        new = cls()
        for key, value in obj.items():
            if hasattr(new, key):
                setattr(new, key, value)
        return new


class PublicationData(DataRow):
    """Layout of the publications table"""

    def __init__(self, pub=Ignore, issue=Ignore, booknum=Ignore, lang=Ignore,
                 title=Ignore, icon=Ignore, failed=Ignore):
        # type: (str, str, int, str, str, str, datetime) -> None
        self.pub = pub
        self.issue = issue
        self.booknum = booknum
        self.lang = lang
        self.title = title
        self.icon = icon
        self.failed = failed


class MediaData(DataRow):
    """Media metadata

    At the moment there is no table for this type of data. It's only used within the Python script.
    """
    def __init__(self, pub=Ignore, issue=Ignore, booknum=Ignore, lang=Ignore,
                 url=Ignore, title=Ignore, duration=Ignore, track=Ignore):
        # type: (str, str, int, str, str, str, int, int) -> None
        self.pub = pub
        self.issue = issue
        self.booknum = booknum
        self.lang = lang
        self.url = url
        self.title = title
        self.duration = duration
        self.track = track


class TranslationData(DataRow):
    """Layout of the translation table"""

    def __init__(self, key=Ignore, lang=Ignore, string=Ignore):
        # type: (str, str, str) -> None
        self.key = key
        self.lang = lang
        self.string = string


class Table(object):
    """Represents a table in the database. Has methods to make basic SQL queries"""

    default_row = DataRow
    name = ''

    def __init__(self, connection):
        # type: (sqlite3.Connection) -> None
        """CREATE TABLE IF NOT EXISTS table (columns)

        Columns are taken from default_row
        """
        self._conn = connection

        assert self.name

        # Declare special type TIMESTAMP for that column that converts it to datetime
        columns = []
        for col in self.default_row().columns():
            if col == 'failed':
                col += ' TIMESTAMP'
            columns.append(col)

        expr = 'CREATE TABLE IF NOT EXISTS {} ({})'.format(self.name, ','.join(columns))
        with self._conn:
            self._conn.execute(expr)

    def insert(self, row):
        # type: (DataRow) -> sqlite3.Cursor
        """INSERT INTO table (columns) VALUES (values)"""
        question_marks = ','.join(['?'] * len(list(row.columns())))
        columns = ','.join(row.columns())
        sql = 'INSERT INTO {} ({}) VALUES ({})'.format(self.name, columns, question_marks)
        with self._conn:
            return self._conn.execute(sql, row.values())

    def delete(self, row):
        # type: (DataRow) -> sqlite3.Cursor
        """DELETE FROM table WHERE conditions"""
        expr, values = where(row.items(include_ignored=False))
        sql = 'DELETE FROM {} WHERE {}'.format(self.name, expr)
        with self._conn:
            return self._conn.execute(sql, values)

    def select(self, row=None):
        # type: (DataRow) -> ()
        """SELECT * FROM table [WHERE conditions]

        Returns a dict which can be used as keyword arguments to create a DataRow
        """
        with self._conn:
            if not row:
                sql = 'SELECT * FROM {}'.format(self.name)
                result = self._conn.execute(sql)
            else:
                expr, values = where(row.items())
                sql = 'SELECT * FROM {} WHERE {}'.format(self.name, expr)
                result = self._conn.execute(sql, values)

            columns = [t[0] for t in result.description]
            for result_row in result:
                # Turn column names and values into a dictionary
                keywords = {col: val for col, val in zip(columns, result_row)}
                #
                yield keywords


def where(items):
    """Return a SQL expression and a list of values to pass to execute()"""

    expr = ''
    tests = []
    values = []
    for key, value in items:
        if value is None:
            tests.append('{} IS NULL'.format(key))
        else:
            tests.append('{} = ?'.format(key))
            values.append(value)
    expr += ' AND '.join(tests)
    return expr, values


# Note: why so many Table classes, and why the same select method in all child classes?
# Well, PyCharm typing isn't smart enough to figure out that the return type will depend
# on the value of "default_row" in the child classes, so I just typed it out explicitly


class PublicationsTable(Table):
    default_row = PublicationData
    name = 'publications'

    def select(self, row=None):
        # type: (DataRow) -> ()
        """SELECT * FROM table [WHERE conditions]"""

        return (PublicationData(**keywords) for keywords in super(PublicationsTable, self).select(row))


class TranslationsTable(Table):
    default_row = TranslationData
    name = 'translations'

    def select(self, row=None):
        # type: (DataRow) -> ()
        """SELECT * FROM table [WHERE conditions]"""

        return (TranslationData(**keywords) for keywords in super(TranslationsTable, self).select(row))


class CacheDatabase(object):
    """Represents the cache database, with tables stored as class attributes"""

    def __init__(self, path):
        # type: (str) -> None
        """Connect to the database and setup tables"""

        self.path = path

        # PARSE_COLNAMES will convert the timestamp string to a datetime
        conn = sqlite3.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES)  # factory=Conn for debugging

        self.publ = PublicationsTable(conn)
        self.trans = TranslationsTable(conn)


class Conn(sqlite3.Connection):
    """For debugging"""

    def execute(self, sql, parameters=None):
        print(sql, parameters)
        return super(Conn, self).execute(sql, parameters or [])
