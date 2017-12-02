# coding: utf-8
import unittest

# Addding assertCountEqual in python 2
if not hasattr(unittest.TestCase, 'assertCountEqual'):
    unittest.TestCase.assertCountEqual = unittest.TestCase.assertItemsEqual

class EnosTest(unittest.TestCase):
    pass

