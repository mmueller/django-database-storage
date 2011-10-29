#!/usr/bin/env python

"""
Run the unit tests for this package.
"""

import os
import re
import sys
import unittest

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(SCRIPT_PATH, 'database_storage')
TEST_PATH = os.path.join(MODULE_PATH, 'test')
STUB_PATH = os.path.join(TEST_PATH, 'stub')

def suite():
    """
    The master test suite. Calls suite() on any *_test.py files and generates
    a test suite containing all module suites.
    """
    test_regex = re.compile("^test_.*.py$")
    files = filter(test_regex.search, os.listdir(TEST_PATH))
    filenameToModuleName = lambda f: os.path.splitext(f)[0]
    moduleNames = map(filenameToModuleName, files)
    modules = map(__import__, moduleNames)
    load = unittest.defaultTestLoader.loadTestsFromModule
    return unittest.TestSuite(map(load, modules))

if __name__ == '__main__':
    sys.path.insert(0, MODULE_PATH)
    sys.path.append(TEST_PATH)
    unittest.TextTestRunner().run(suite())

