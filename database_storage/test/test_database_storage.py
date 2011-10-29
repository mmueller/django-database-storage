import django
import imp
import mock
import random
import sqlite3
import StringIO
import sys
import unittest

from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist
from django.core.files import File

# Stub out the django.db module before importing DatabaseStorage
django.db = imp.new_module('django.db')
sys.modules['django.db'] = django.db

# Temporarily mock the two database objects that DatabaseStorage uses
django.db.connection = mock.Mock()
django.db.transaction = mock.Mock()

# Finally import DatabaseStorage and test it
import database_storage
from database_storage import DatabaseStorage

DEFAULT_OPTIONS = {
    'table': 'files',
    'base_url': 'base_url/',
}

CREATE_TABLE = """
    CREATE TABLE files (
        filename vARCHAR(256) NOT NULL PRIMARY KEY,
        data TEXT NOT NULL,
        size INTEGER NOT NULL
    );
"""

class TestSequenceFunctions(unittest.TestCase):
    "Unit tests for the DatabaseStorage class."

    def setUp(self):
        # Reset the mock objects
        database_storage.connection = self._connect_database()
        database_storage.transaction.reset_mock()

    def test_missing_options(self):
        self.assertRaises(ImproperlyConfigured, DatabaseStorage, {})

    def test_unknown_option(self):
        options = { 'unknown': '' }
        self.assertRaises(ImproperlyConfigured, DatabaseStorage, options)

    def test_default_options(self):
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        self.assertEqual('filename', storage.name_column)
        self.assertEqual('data', storage.data_column)
        self.assertEqual('size', storage.size_column)

    def test_open_missing_file(self):
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        self.assertTrue(storage._open('some_file') is None)

    def test_save_and_retrieve(self):
        "Test saving and retrieving a 100KB binary file."
        name = 'foo.bin'
        content = self._get_binary_data(100 * 1024)
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        storage._save(name, self._wrap_content(content))
        self.assertEqual(storage._open(name).read(), content)

    def test_overwrite(self):
        "Overwrite a file with new content, verify it updates correctly."
        name = 'foo.bin'
        content = self._get_binary_data(50 * 1024)
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        storage._save(name, self._wrap_content(content))
        self.assertEqual(storage.size(name), 50 * 1024)
        self.assertEqual(storage._open(name).read(), content)

        new_content = self._get_binary_data(35 * 1024)
        storage._save(name, self._wrap_content(new_content))
        self.assertEqual(storage.size(name), 35 * 1024)
        self.assertEqual(storage._open(name).read(), new_content)

    def test_empty_file(self):
        "Save an empty file and test that all methods are well-behaved."
        name = 'foo.bin'
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        storage._save(name, self._wrap_content(''))
        self.assertTrue(storage.exists(name))
        self.assertEqual(storage.size(name), 0)
        self.assertEqual(storage._open(name).read(), '')

    def test_exists(self):
        "Test exists() for both true & false cases."
        name = 'foo.bin'
        content = self._get_binary_data(1024)
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        storage._save(name, self._wrap_content(content))
        self.assertTrue(storage.exists(name))
        self.assertFalse(storage.exists('bar.bin'))

    def test_delete(self):
        "Save and delete a file, verify it existed and then is removed."
        name = 'foo.bin'
        content = self._get_binary_data(1024)
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        storage._save(name, self._wrap_content(content))
        self.assertTrue(storage.exists(name))
        storage.delete(name)
        self.assertFalse(storage.exists(name))

    def test_delete_nonexistent(self):
        "Delete a file that does not exist, should silently succeed."
        name = 'foo.bin'
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        self.assertFalse(storage.exists(name))
        storage.delete(name)
        self.assertFalse(storage.exists(name))

    def test_path(self):
        "Verify that path() raises NotImplementedError."
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        self.assertRaises(NotImplementedError, storage.path, 'foo.bin')

    def test_url(self):
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        self.assertEqual(storage.url('foo\\bar.jpg'), 'base_url/foo/bar.jpg')

    def test_size(self):
        "Save a 12,345 byte file and verify size() reports correctly."
        name = 'foo.bin'
        content = self._get_binary_data(12345)
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        storage._save(name, self._wrap_content(content))
        self.assertEqual(storage.size(name), 12345)

    def test_size_nonexistent(self):
        name = 'foo.bin'
        storage = DatabaseStorage(DEFAULT_OPTIONS)
        self.assertRaises(ObjectDoesNotExist, storage.size, name)

    def _connect_database(self):
        "Create an in-memory database for a test case."
        conn = ConnectionWrapper(sqlite3.connect(':memory:'))
        conn.cursor().execute(CREATE_TABLE);
        return conn

    def _get_binary_data(self, size):
        "Get randomly-generated data of the given size."
        content = ''
        for i in xrange(0, size):
            content += chr(random.randint(0, 255))
        return content

    def _wrap_content(self, content):
        "Wrap string data into a File object."
        s = StringIO.StringIO(content)
        return File(s)

# Patch sqlite's execute method to accept "%s" for parameters (the way Django
# connection objects work).  Monkey patching was not an option because the
# sqlite3 classes are old style, so wrappers are used instead.
class ConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn

    def __getattr__(self, n):
        "Passthru to the underlying conn object except for 'cursor'."
        def new_cursor(self):
            return CursorWrapper(self.conn.cursor())
        if n == 'cursor':
            return new_cursor.__get__(self, ConnectionWrapper)
        return getattr(self.conn, n)

class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def __getattr__(self, n):
        "Passthru to the underlying cursor object except for 'execute'."
        def new_execute(self, query, *args):
            return self.cursor.execute(query.replace("%s", "?"), *args)
        if n == 'execute':
            return new_execute.__get__(self, CursorWrapper)
        return getattr(self.cursor, n)
