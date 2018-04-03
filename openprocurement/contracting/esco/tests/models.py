# -*- coding: utf-8 -*-
import unittest

from datetime import timedelta
from mock import patch, MagicMock

from openprocurement.api.utils import get_now
from openprocurement.contracting.esco.models import Milestone


class TestMilestone(unittest.TestCase):

    def test_validate_status(self):
        milestone_data = {
            "sequenceNumber": 1,
            "title": "Begin of milestones era",
            "period": {
                "startDate": "2017-01-01T00:00:00.000000+02:00",
                "endDate": "2018-01-01T00:00:00.000000+02:00"
            },
            "value": {
                'amount': 1000,
                'currency': 'UAH',
                'valueAddedTaxIncluded': True
            }
        }
        milestone = Milestone(milestone_data)
        milestone.validate()
        # import pdb; pdb.set_trace()



def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestMilestone))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
