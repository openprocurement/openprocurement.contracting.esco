# -*- coding: utf-8 -*-

import unittest

from openprocurement.contract.esco.tests import contract, document, change


def suite():
    suite = unittest.TestSuite()
    suite.addTest(contract.suite())
    suite.addTest(document.suite())
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
