# -*- coding: utf-8 -*-
import os
import json
from copy import deepcopy
from uuid import uuid4
from datetime import timedelta

from mock import patch

from openprocurement.api.constants import SANDBOX_MODE
from openprocurement.api.utils import get_now
from openprocurement.contracting.api.tests.base import (
    BaseWebTest as BaseBaseWebTest
)

from openprocurement.contracting.core.tests.base import documents
from openprocurement.contracting.esco.utils import generate_milestones


# test_contract_data = deepcopy(base_test_contract_data)
contract_data_json = "{}/data/test_contract_data.json".format(
    os.path.dirname(__file__)
)
with open(contract_data_json) as f:
    test_contract_data = json.loads(f.read())

# dates generation
now = get_now()
test_contract_data["dateSigned"] = now.isoformat()
test_contract_data["noticePublicationDate"] = now.isoformat()
test_contract_data["period"]["startDate"] = now.isoformat()

days = test_contract_data["value"]["contractDuration"]["days"]
years = test_contract_data["value"]["contractDuration"]["years"]
contractEndDate = now.replace(year=now.year + years) + timedelta(days=days)
test_contract_data["period"]["endDate"] = contractEndDate.isoformat()

if SANDBOX_MODE:
    test_contract_data['procurementMethodDetails'] = 'quick, accelerator=1440'

test_contract_data['milestones'] = generate_milestones(test_contract_data)


class BaseWebTest(BaseBaseWebTest):
    """Base Web Test to test openprocurement.contracting.esco.

    It setups the database before each test and delete it after.
    """
    initial_auth = ('Basic', ('token', ''))
    docservice = False
    relative_to = os.path.dirname(__file__)


class BaseContractWebTest(BaseWebTest):
    initial_data = test_contract_data

    def setUp(self):
        super(BaseContractWebTest, self).setUp()
        self.create_contract()

    def create_contract(self):
        data = deepcopy(self.initial_data)

        orig_auth = self.app.authorization
        self.app.authorization = ('Basic', ('contracting', ''))
        response = self.app.post_json('/contracts', {'data': data})
        self.contract = response.json['data']
        self.contract_token = response.json['access']['token']
        self.contract_id = self.contract['id']
        self.app.authorization = orig_auth

    def terminate_milestones(self):
        self.tender_token = self.initial_data['tender_token']
        response = self.app.get('/contracts/{}'.format(self.contract_id))
        contract = response.json['data']

        # terminate all scheduled milestones in met
        now = get_now()
        # time travel to contract.period.endDate
        with patch('openprocurement.contracting.esco.validation.get_now') as mocked_get_now:
            contract_duration_years = self.initial_data['value']['contractDuration']['years']
            contract_duration_days = self.initial_data['value']['contractDuration']['days']
            mocked_get_now.return_value = \
                now.replace(year=now.year + contract_duration_years) + timedelta(days=contract_duration_days)
            for milestone in contract['milestones']:
                if milestone['status'] not in ['notMet', 'partiallyMet', 'met']:
                    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
                        self.contract_id, milestone['id'], self.contract_token), {'data': {
                            "amountPaid": {"amount": milestone['value']['amount']}, 'status': 'met'}})

    def terminate_contract(self):
        self.terminate_milestones()
        response = self.app.patch_json('/contracts/{}?acc_token={}'.format(self.contract_id, self.contract_token),
                                       {"data": {"status": "terminated"}})

    def tearDown(self):
        del self.db[self.contract_id]
        super(BaseContractWebTest, self).tearDown()


class BaseTerminatedContractWebTest(BaseContractWebTest):

    def setUp(self):
        super(BaseTerminatedContractWebTest, self).setUp()
        self.terminate_contract()


class BaseContractTerminatedMilestonesWebTest(BaseContractWebTest):

    def setUp(self):
        super(BaseContractTerminatedMilestonesWebTest, self).setUp()
        self.terminate_milestones()


class BaseContractContentWebTest(BaseContractWebTest):
    def setUp(self):
        super(BaseContractContentWebTest, self).setUp()
        response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(
            self.contract_id, self.initial_data['tender_token']), {'data': {}})
        self.contract_token = response.json['access']['token']
