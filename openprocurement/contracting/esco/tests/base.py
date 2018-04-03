# -*- coding: utf-8 -*-
import os
import json
from copy import deepcopy
from uuid import uuid4

from openprocurement.api.utils import get_now
from openprocurement.contracting.api.tests.base import (
    BaseWebTest as BaseBaseWebTest
)

from openprocurement.contracting.core.tests.base import documents


NBU_DISCOUNT_RATE = 0.135

# test_contract_data = deepcopy(base_test_contract_data)
contract_data_json = "{}/data/test_contract_data.json".format(
    os.path.dirname(__file__)
)
with open(contract_data_json) as f:
    test_contract_data = json.loads(f.read())
test_contract_data['id'] = uuid4().hex
test_contract_data['contractType'] = 'esco'
test_contract_data['NBUdiscountRate'] = NBU_DISCOUNT_RATE
test_contract_data["yearlyPaymentsPercentageRange"] = 0.8
test_contract_data["dateSigned"] = get_now().isoformat()
# test_contract_data['value'] = {'yearlyPayments': 0.9,
#                                'annualCostsReduction': 751.5,
#                                'contractDuration': 10}


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
        # self.contract_token = response.json['access']['token']
        self.contract_id = self.contract['id']
        self.app.authorization = orig_auth

    def tearDown(self):
        del self.db[self.contract_id]
        super(BaseContractWebTest, self).tearDown()


class BaseContractContentWebTest(BaseContractWebTest):
    def setUp(self):
        super(BaseContractContentWebTest, self).setUp()
        response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(
            self.contract_id, self.initial_data['tender_token']), {'data': {}})
        self.contract_token = response.json['access']['token']
