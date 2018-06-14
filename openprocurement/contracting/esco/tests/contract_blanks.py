# -*- coding: utf-8 -*-
from copy import deepcopy
from iso8601 import parse_date
from uuid import uuid4
from datetime import timedelta

from mock import patch
from munch import munchify

from openprocurement.api.utils import get_now
from openprocurement.contracting.esco.constants import DAYS_PER_YEAR
from openprocurement.contracting.esco.models import Contract
from openprocurement.contracting.esco.utils import update_delta


# ContractTest


def simple_add_esco_contract(self):
    u = Contract(self.initial_data)
    u.contractID = "UA-C"

    assert u.id == self.initial_data['id']
    assert u.doc_id == self.initial_data['id']
    assert u.rev is None

    u.store(self.db)

    assert u.id == self.initial_data['id']
    assert u.rev is not None

    fromdb = self.db.get(u.id)

    assert u.contractID == fromdb['contractID']
    assert u.doc_type == "Contract"

    u.delete_instance(self.db)

# ContractResourceTest

def esco_contract_milestones_check(self):
    response = self.app.get('/contracts')
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(len(response.json['data']), 0)

    response = self.app.post_json('/contracts', {"data": self.initial_data})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    contract = response.json['data']
    self.assertEqual(contract['status'], 'active')

    response = self.app.get('/contracts/{}'.format(contract['id']))
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    data = response.json['data']['milestones']
    self.assertEqual(len(data), 8)
    sequenceNumber = 1
    for milestone in data:
        if sequenceNumber == 1:
            self.assertEqual(milestone['status'], 'pending')
        else:
            self.assertEqual(milestone['status'], 'scheduled')
        self.assertEqual(milestone['sequenceNumber'], sequenceNumber)
        sequenceNumber += 1


def create_contract(self):
    response = self.app.get('/contracts')
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(len(response.json['data']), 0)

    response = self.app.post_json('/contracts', {"data": self.initial_data})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    contract = response.json['data']
    self.assertEqual(contract['status'], 'active')

    response = self.app.get('/contracts/{}'.format(contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(set(response.json['data']), set(contract))
    self.assertEqual(response.json['data'], contract)
    self.assertEqual(set(response.json['data'].keys()),
                     {u'status', u'milestones', u'tender_id', u'description', u'title', u'items', u'suppliers',
                      u'contractNumber', u'period', u'value', u'dateModified', u'owner', u'procuringEntity',
                      u'NBUdiscountRate', u'dateSigned', u'contractType', u'awardID', u'amountPaid', u'id',
                      u'contractID', u'fundingKind', u'yearlyPaymentsPercentageRange', u'noticePublicationDate'}
                     )

    data = deepcopy(self.initial_data)
    data['id'] = uuid4().hex
    response = self.app.post_json('/contracts?opt_jsonp=callback', {"data": data})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/javascript')
    self.assertIn('callback({"', response.body)

    data['id'] = uuid4().hex
    response = self.app.post_json('/contracts?opt_pretty=1', {"data": data})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertIn('{\n    "', response.body)

    data['id'] = uuid4().hex
    response = self.app.post_json('/contracts', {"data": data, "options": {"pretty": True}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertIn('{\n    "', response.body)

    # broker has no permissions to create contract
    self.app.authorization = ('Basic', ('broker', ''))
    response = self.app.post_json('/contracts', {"data": self.initial_data}, status=403)
    self.assertEqual(response.status, '403 Forbidden')


def create_contract_generated(self):
    data = self.initial_data.copy()
    data.update({'id': uuid4().hex, 'doc_id': uuid4().hex, 'contractID': uuid4().hex})
    response = self.app.post_json('/contracts', {'data': data})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    contract = response.json['data']
    self.assertEqual(set(contract), set([
        u'id', u'dateModified', u'contractID', u'status', u'suppliers',
        u'contractNumber', u'period', u'dateSigned', u'value', u'awardID',
        u'items', u'owner', u'tender_id', u'procuringEntity', u'contractType',
        u'NBUdiscountRate', u'value', u'description', u'title', u'milestones',
        u'amountPaid', u'noticePublicationDate', u'fundingKind', u'yearlyPaymentsPercentageRange']))
    self.assertEqual(data['id'], contract['id'])
    self.assertNotEqual(data['doc_id'], contract['id'])
    self.assertEqual(data['contractID'], contract['contractID'])


def patch_contract_NBUdiscountRate(self):
    response = self.app.post_json('/contracts', {"data": self.initial_data})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    contract = response.json['data']
    tender_token = self.initial_data['tender_token']
    self.assertIn('NBUdiscountRate', response.json['data'])
    self.assertEqual(contract['NBUdiscountRate'], self.initial_data['NBUdiscountRate'])
    self.assertNotEqual(response.json['data']['NBUdiscountRate'], 0.33)

    response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(contract['id'], tender_token),
                                   {'data': ''})
    self.assertEqual(response.status, '200 OK')
    token = response.json['access']['token']

    # NBUdiscountRate field forbidden for patch
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(contract['id'], token),
                                   {'data': {'NBUdiscountRate': 0.33}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json, None)

    response = self.app.get('/contracts/{}'.format(contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['NBUdiscountRate'], self.initial_data['NBUdiscountRate'])


def patch_terminated_contract_NBUdiscountRate(self):
    # check NBUdiscountRate patch for teminated contract
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'terminated')

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(self.contract_id, self.contract_token),
                                   {'data': {'NBUdiscountRate': 0.33}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')

    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['NBUdiscountRate'], self.initial_data['NBUdiscountRate'])


def contract_type_check(self):
    expected_contract_type = getattr(self, 'contract_type')
    response = self.app.post_json('/contracts', {"data": self.initial_data})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    contract = response.json['data']
    tender_token = self.initial_data['tender_token']
    self.assertIn('contractType', response.json['data'])
    self.assertEqual(contract['contractType'], expected_contract_type)

    response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(contract['id'], tender_token),
                                   {'data': ''})
    self.assertEqual(response.status, '200 OK')
    token = response.json['access']['token']

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(contract['id'], token),
        {'data': {'contractType': 'common'}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}'.format(contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertNotEqual(response.json['data']['contractType'], 'common')
    self.assertEqual(response.json['data']['contractType'], 'esco')


def patch_tender_contract(self):
    response = self.app.patch_json('/contracts/{}'.format(
        self.contract['id']), {"data": {"title": "New Title"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')

    tender_token = self.initial_data['tender_token']
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], tender_token), {"data": {"title": "New Title"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')

    response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(
        self.contract['id'], tender_token), {'data': ''})
    self.assertEqual(response.status, '200 OK')
    token = response.json['access']['token']

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"title": "New Title"}})
    self.assertEqual(response.status, '200 OK')
    if 'mode' in self.initial_data and self.initial_data['mode'] == u'test':
        self.assertEqual(response.json['data']['title'], u"[ТЕСТУВАННЯ] New Title")
    else:
        self.assertEqual(response.json['data']['title'], "New Title")

    # can't patch contract amountPaid amount, currency and vat
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {
            "amountPaid": {"amount": 900, "currency": "USD", "valueAddedTaxIncluded": False}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.body, 'null')

    # check milestone amountPaid change
    # get correct pending milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]
    # make sure it's pending milestone!
    self.assertEqual(milestone['status'], 'pending')

    # update amountPaid of milestone
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], token), {'data': {
            "amountPaid": {"amount": 100000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json["data"]["amountPaid"]["amount"], 100000)

    # contract amountPaid.amount not changed, equal sum of milestones.amountPaid
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {
            "amountPaid": {"amount": 900, "currency": "USD", "valueAddedTaxIncluded": False}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['amountPaid']['amount'], 100000)
    self.assertEqual(response.json['data']['amountPaid']['currency'], "UAH")
    self.assertEqual(response.json['data']['amountPaid']['valueAddedTaxIncluded'], True)

    contract = response.json['data']

    # can't patch value amount, currency and vat
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"value": {'amount': 1000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.body, 'null')

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"value": {"currency": "USD", "valueAddedTaxIncluded": False}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    # value is calculated from milestones
    milestones_value = sum(x['value']['amount'] for x in response.json['data']['milestones'])
    self.assertEqual(response.json['data']['value']['amount'], round(milestones_value, 2))
    self.assertEqual(response.json['data']['value']['currency'], self.initial_data['value']['currency'])
    self.assertEqual(response.json['data']['value']['valueAddedTaxIncluded'], self.initial_data['value']['valueAddedTaxIncluded'])

    # can't patch milestones from contract
    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestones = response.json['data']['milestones']

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"milestones": []}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.body, 'null')

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"milestones": [{'title': 'new title'}, {}, {}]}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertNotEqual(response.json['data']['milestones'][0]['title'], 'new title')
    self.assertEqual(len(response.json['data']['milestones']), len(milestones))
    self.assertEqual(response.json['data']['milestones'], milestones)

    # testing that amountPaid and value doesn't include amount from spare milestones
    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertIn('milestones', response.json['data'])

    contract_period = response.json['data']['period']
    start_amountPaid = response.json['data']['amountPaid']['amount']
    start_value = response.json['data']['value']['amount']
    number_of_milestones = len(response.json['data']['milestones'])
    end_date = parse_date(response.json['data']['period']['endDate'])

    #  create pending change for patching contract
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract['id'], token), {'data': self.pending_change})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')

    delta = timedelta(days=DAYS_PER_YEAR)
    delta = update_delta(delta, munchify(self.initial_data))
    new_end_date = end_date + delta
    contract_period['endDate'] = new_end_date.isoformat()
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
            self.contract['id'], token), {"data": {"period": contract_period}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(len(response.json['data']['milestones']), number_of_milestones + 1)

    target_milestone = response.json['data']['milestones'][number_of_milestones]
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract['id'], target_milestone['id'], token), {'data': {"value": {"amount": 500}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['value']['amount'], 500.0)
    # time travel to change milestone amountPaid amount, cant change with patch
    contract = self.db.get(self.contract['id'])
    contract['milestones'][number_of_milestones]['amountPaid']['amount'] = u'500.00'
    self.db.save(contract)

    # check that value and amountPaid are increased
    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['amountPaid']['amount'], start_amountPaid + 500)
    self.assertEqual(response.json['data']['value']['amount'], start_value + 500)

    #  now change endDate back for year to hide milestone to spare
    #  and check amount and amountPaid are decreased
    delta = timedelta(days=DAYS_PER_YEAR)
    delta = update_delta(delta, munchify(self.initial_data))
    new_end_date = new_end_date - delta
    contract_period['endDate'] = new_end_date.isoformat()

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"period": contract_period}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['period']['endDate'], new_end_date.isoformat())
    self.assertEqual(response.json['data']['amountPaid']['amount'], start_amountPaid)
    self.assertEqual(response.json['data']['value']['amount'], start_value)


def patch_tender_terminated_contract(self):
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'terminated')

    response = self.app.patch_json(
        '/contracts/{}?acc_token={}'.format(self.contract_id, self.contract_token),
        {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(self.contract_id, self.contract_token),
                                   {"data": {"title": "fff"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')

    response = self.app.patch_json('/contracts/some_id', {"data": {"status": "active"}}, status=404)
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['status'], 'error')
    self.assertEqual(response.json['errors'], [
        {u'description': u'Not Found', u'location':
         u'url', u'name': u'contract_id'}
    ])


def patch_tender_contract_period(self):
    tender_token = self.initial_data['tender_token']
    response = self.app.patch_json(
        '/contracts/{}/credentials?acc_token={}'.format(
            self.contract['id'], tender_token), {'data': ''})
    self.assertEqual(response.status, '200 OK')
    token = response.json['access']['token']

    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['milestones'][0]['status'],
                     'pending')
    self.assertLess(len(response.json['data']['milestones']), 17)

    contract_period = response.json['data']['period']

    #  get pending milestone
    response = self.app.get(
        '/contracts/{}/milestones'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    pending_milestone = response.json['data'][0]
    milestone_startDate = parse_date(pending_milestone['period']['startDate'])

    # contract period endDate = pending milestone startDate - timedelta days = 1
    delta = timedelta(days=1)
    delta = update_delta(delta, munchify(self.initial_data))
    contract_period['endDate'] = (milestone_startDate - delta).isoformat()

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token),
        {"data": {"period": contract_period}}, status=422)
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'], [{u'description': {
        u'startDate': [u'period should begin before its end']},
        u'location': u'body',
        u'name': u'period'}])

    # update first milestone to notMet, second becomes pending
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract['id'], pending_milestone['id'], token),
        {"data": {"status": 'notMet'}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'notMet')

    #  get pending milestone
    response = self.app.get(
        '/contracts/{}/milestones'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    pending_milestone = response.json['data'][1]
    milestone_startDate = parse_date(pending_milestone['period']['startDate'])

    # contract period endDate == pending milestone startDate
    delta = timedelta(days=1)
    delta = update_delta(delta, munchify(self.initial_data))
    contract_period['endDate'] = (milestone_startDate - delta).isoformat()

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token),
        {"data": {"period": contract_period}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'], [{
        u'description': u"Can't update endDate of contract without pending change",
        u'location': u'body', u'name': u'data'
    }])

    #  create pending change
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract['id'], token), {'data': self.pending_change})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')

    #  test  contract endDate is less than pending milestone startDate
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token),
        {"data": {"period": contract_period}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'], [{
        u'description': u"Can't update contract endDate, if it is less than pending milestone startDate",
        u'location': u'body', u'name': u'data'}])

    #  test cant change contract period startDate, timedelta 1 day
    temp_startDate = contract_period['startDate']
    contract_period['endDate'] = milestone_startDate.isoformat()
    delta = timedelta(days=1)
    delta = update_delta(delta, munchify(self.initial_data))
    contract_period['startDate'] = (parse_date(contract_period['endDate']) - delta).isoformat()

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"period": contract_period}},
        status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data",
         "description": "Can't change startDate of contract"}])

    # now we set up saved startDate contract can be changed
    contract_period['startDate'] = temp_startDate
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"period": contract_period}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['period']['endDate'],
                     contract_period['endDate'])
    # no scheduled milestones
    self.assertEqual([m['status'] for m in response.json['data']['milestones']],
                     [u'notMet', u'pending'])
    self.assertEqual(
        response.json['data']['milestones'][-1]['period']['endDate'],
        contract_period['endDate'])

    # change endDate +2 days only, no years
    delta = timedelta(days=2)
    delta = update_delta(delta, munchify(self.initial_data))
    contract_period['endDate'] = (parse_date(contract_period['endDate']) + delta).isoformat()

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"period": contract_period}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['period']['endDate'],
                     contract_period['endDate'])
    self.assertEqual(
        [m['status'] for m in response.json['data']['milestones']],
        [u'notMet', u'pending'])
    self.assertEqual(
        response.json['data']['milestones'][-1]['period']['endDate'],
        contract_period['endDate'])

    # test contract endDate over 15 years ( by one day), error should be
    count_sheduled_milestones = 15
    contract_period_start_date = parse_date(contract_period['startDate'])
    contract_period_end_date = contract_period_start_date.replace(
        contract_period_start_date.year + count_sheduled_milestones) + timedelta(
        days=1)
    contract_period['endDate'] = contract_period_end_date.isoformat()

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token),
        {"data": {"period": contract_period}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'], [{
        u'description': u'Contract period cannot be over 15 years',
        u'location': u'body', u'name': u'data'}])

    #  test change endDate of contract is 15 years from startDate
    delta = timedelta(days=DAYS_PER_YEAR * count_sheduled_milestones)
    delta = update_delta(delta, munchify(self.initial_data))
    contract_period_end_date = contract_period_start_date + delta

    contract_period['endDate'] = contract_period_end_date.isoformat()
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"period": contract_period}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['period']['endDate'],
                     contract_period['endDate'])
    self.assertEqual(
        [x['status'] for x in response.json['data']['milestones']],
        [u'notMet', u'pending'] + [u'scheduled'] * (
                count_sheduled_milestones - 1))
    self.assertLess(len(response.json['data']['milestones']), 17)

    #  test shrinking last milestone for 3 days
    delta = timedelta(days=DAYS_PER_YEAR * count_sheduled_milestones) - timedelta(days=3)
    delta = update_delta(delta, munchify(self.initial_data))
    contract_period_end_date = contract_period_start_date + delta

    contract_period['endDate'] = contract_period_end_date.isoformat()
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"period": contract_period}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['period']['endDate'],
                     contract_period['endDate'])
    self.assertEqual(
        [x['status'] for x in response.json['data']['milestones']],
        [u'notMet', u'pending'] + [u'scheduled'] * (
                count_sheduled_milestones - 1))

    #  test for shrinking milestones, for 4 years
    count_sheduled_milestones -= 4
    delta = timedelta(days=DAYS_PER_YEAR * count_sheduled_milestones)
    delta = update_delta(delta, munchify(self.initial_data))
    contract_period_end_date = contract_period_start_date + delta
    contract_period['endDate'] = contract_period_end_date.isoformat()

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token),
        {"data": {"period": contract_period}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['period']['endDate'],
                     contract_period['endDate'])
    self.assertEqual(
        response.json['data']['milestones'][-1]['period']['endDate'],
        contract_period['endDate'])
    self.assertEqual(
        [x['status'] for x in response.json['data']['milestones']],
        [u'notMet', u'pending'] + [u'scheduled'] * (count_sheduled_milestones-1))

    # close all milestones to spare, so we have only 2 milestones notMet and pending
    contract_period['endDate'] = pending_milestone['period']['startDate']

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token),
        {"data": {"period": contract_period}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['period']['endDate'],
                     contract_period['endDate'])
    self.assertEqual(
        response.json['data']['milestones'][-1]['period']['endDate'],
        contract_period['endDate'])
    self.assertEqual([x['status'] for x in response.json['data']['milestones']],
                     [u'notMet', u'pending'])

    # time travel to change milestone status
    contract = self.db.get(self.contract['id'])
    contract['milestones'][1]['period']['startDate'] = get_now().isoformat()
    self.db.save(contract)

    # update first milestone to notMet
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract['id'], pending_milestone['id'], token),
        {"data": {"status": 'notMet'}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'notMet')

    contract_period['endDate'] = \
        (parse_date(contract_period['endDate']) + timedelta(days=1)).isoformat()
    # test all milestones in terminated statuses change contract endDate
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"period": contract_period}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['errors'], [{
        u'description': u"Can't update contract endDate, all milestones are in terminated statuses",
        u'location': u'body', u'name': u'data'}])


def contract_administrator_change(self):
    response = self.app.patch_json('/contracts/{}'.format(self.contract['id']),
                                   {'data': {'mode': u'test',
                                             "suppliers": [{
                                                "contactPoint": {
                                                    "email": "fff@gmail.com",
                                                },
                                                "address": {"postalCode": "79014"}
                                             }],
                                             'procuringEntity': {"identifier": {"id": "11111111"},
                                                                 "contactPoint": {"telephone": "102"}}
                                             }})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['mode'], u'test')
    self.assertEqual(response.json['data']["procuringEntity"]["identifier"]["id"], "11111111")
    self.assertEqual(response.json['data']["procuringEntity"]["contactPoint"]["telephone"], "102")
    self.assertEqual(response.json['data']["suppliers"][0]["contactPoint"]["email"], "fff@gmail.com")
    self.assertEqual(
        response.json['data']["suppliers"][0]["contactPoint"]["telephone"],
        self.initial_data['suppliers'][0]['contactPoint']['telephone']
    )
    self.assertEqual(response.json['data']["suppliers"][0]["address"]["postalCode"], "79014")
    self.assertEqual(response.json['data']["suppliers"][0]["address"]["countryName"], u"Україна") # old field value left untouchable
    # administrator has permissions to update only: mode, procuringEntity, suppliers
    response = self.app.patch_json('/contracts/{}'.format(self.contract['id']), {'data': {
        'value': {'amount': 100500},
        'id': '1234' * 8,
        'owner': 'kapitoshka',
        'contractID': "UA-00-00-00",
        'dateSigned': get_now().isoformat(),
    }})
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    # value is calculated from milestones
    milestones_value = sum(x['value']['amount'] for x in response.json['data']['milestones'])
    self.assertEqual(response.json['data']['value']['amount'], round(milestones_value, 2))
    self.assertEqual(response.json['data']['id'], self.initial_data['id'])
    self.assertEqual(response.json['data']['owner'], self.initial_data['owner'])
    self.assertEqual(response.json['data']['contractID'], self.initial_data['contractID'])
    self.assertEqual(response.json['data']['dateSigned'], self.initial_data['dateSigned'])


def contract_status_change_with_termination_details(self):
    tender_token = self.initial_data['tender_token']

    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    contract = response.json['data']

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], tender_token), {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')

    response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(
        self.contract['id'], tender_token), {'data': ''})
    self.assertEqual(response.status, '200 OK')
    token = response.json['access']['token']

    # active > terminated allowed
    # get correct pending milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]
    # make sure it's pending milestone!
    self.assertEqual(milestone['status'], 'pending')

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], token), {'data': {
            "amountPaid": {"amount": 100000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json["data"]["amountPaid"]["amount"], 100000)

    # terminate all scheduled milestones in partiallyMet but first milestone in met
    now = get_now()
    # time travel to contract.period.endDate
    with patch('openprocurement.contracting.esco.validation.get_now') as mocked_get_now:
        contract_duration_years = self.initial_data['value']['contractDuration']['years']
        contract_duration_days = self.initial_data['value']['contractDuration']['days']
        mocked_get_now.return_value = \
            now.replace(year=now.year + contract_duration_years) + timedelta(days=contract_duration_days)
        for milestone in contract['milestones']:
            if milestone['sequenceNumber'] == 1:
                response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
                    self.contract_id, milestone['id'], token), {'data': {
                        "amountPaid": {"amount": milestone['value']['amount']}, 'status': 'met'}})
                self.assertEqual(response.status, '200 OK')
                self.assertEqual(response.json['data']['status'], 'met')
            else:
                amount = milestone['value']['amount'] - 10

                response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
                    self.contract_id, milestone['id'], token), {'data': {
                        "amountPaid": {"amount": amount}, 'status': 'partiallyMet'}})
                self.assertEqual(response.status, '200 OK')
                self.assertEqual(response.json['data']['status'], 'partiallyMet')
                self.assertEqual(response.json['data']['amountPaid']['amount'], amount)

    # make sure that contract without non-terminated milestones
    # and contact.amountPaid.amount less than contract.value.amount
    contract = self.app.get('/contracts/{}'.format(self.contract['id'])).json['data']
    self.assertLess(contract['amountPaid']['amount'], contract['value']['amount'])
    self.assertEqual(
        False,
        any(milestone['status'] in ['pending', 'scheduled'] for milestone in contract['milestones'])
    )

    # try terminate contract without terminationDetails
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"status": "terminated"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u'terminationDetails is required.',
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    termination_details = 'I\'m Scrooge McDuck'
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"status": "terminated", 'terminationDetails': termination_details}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'terminated')
    self.assertEqual(response.json['data']['terminationDetails'], termination_details)

    # terminated > active not allowed
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')


def contract_status_change_with_not_met(self):
    tender_token = self.initial_data['tender_token']

    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    contract = response.json['data']

    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], tender_token), {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')

    response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(
        self.contract['id'], tender_token), {'data': ''})
    self.assertEqual(response.status, '200 OK')
    token = response.json['access']['token']

    # active > terminated allowed
    # get correct pending milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]
    # make sure it's pending milestone!
    self.assertEqual(milestone['status'], 'pending')

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], token), {'data': {
            "amountPaid": {"amount": 100000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json["data"]["amountPaid"]["amount"], 100000)


    # terminate all scheduled milestones in notMet but first milestone in met
    now = get_now()
    # time travel to contract.period.endDate
    with patch('openprocurement.contracting.esco.validation.get_now') as mocked_get_now:
        contract_duration_years = self.initial_data['value']['contractDuration']['years']
        contract_duration_days = self.initial_data['value']['contractDuration']['days']
        mocked_get_now.return_value = \
            now.replace(year=now.year + contract_duration_years) + timedelta(days=contract_duration_days)
        for milestone in contract['milestones']:
            if milestone['sequenceNumber'] == 1:
                response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
                    self.contract_id, milestone['id'], token), {'data': {
                        "amountPaid": {"amount": milestone['value']['amount']}, 'status': 'met'}})
                self.assertEqual(response.status, '200 OK')
                self.assertEqual(response.json['data']['status'], 'met')
            else:
                amount = 0
                response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
                    self.contract_id, milestone['id'], token), {'data': {
                        "amountPaid": {"amount": amount}, 'status': 'notMet'}})
                self.assertEqual(response.status, '200 OK')
                self.assertEqual(response.json['data']['status'], 'notMet')
                self.assertEqual(response.json['data']['amountPaid']['amount'], amount)

    # make sure that contract without non-terminated milestones
    # and contact.amountPaid.amount equal 0
    contract = self.app.get('/contracts/{}'.format(self.contract['id'])).json['data']
    self.assertEqual(contract['amountPaid']['amount'], 0)
    self.assertEqual(
        False,
        any(milestone['status'] in ['pending', 'scheduled'] for milestone in contract['milestones'])
    )

    # try terminate contract without terminationDetails
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"status": "terminated"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u'terminationDetails is required.',
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    termination_details = 'I\'m Scrooge McDuck'
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"status": "terminated", 'terminationDetails': termination_details}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'terminated')
    self.assertEqual(response.json['data']['terminationDetails'], termination_details)

    # terminated > active not allowed
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"status": "active"}}, status=403)
    self.assertEqual(response.status, '403 Forbidden')


def contract_status_change_wo_termination_details(self):
    tender_token = self.initial_data['tender_token']

    response = self.app.get('/contracts/{}'.format(self.contract['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    contract = response.json['data']

    response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(
        self.contract['id'], tender_token), {'data': ''})
    self.assertEqual(response.status, '200 OK')
    token = response.json['access']['token']

    # active > terminated allowed
    # get correct pending milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]

    # make sure that contract have non-terminated milestones
    self.assertEqual(
        True,
        any(milestone['status'] in ['pending', 'spare', 'scheduled'] for milestone in contract['milestones'])
    )

    # terminate all scheduled milestones in met
    now = get_now()
    # time travel to contract.period.endDate
    with patch('openprocurement.contracting.esco.validation.get_now') as mocked_get_now:
        contract_duration_years = self.initial_data['value']['contractDuration']['years']
        contract_duration_days = self.initial_data['value']['contractDuration']['days']
        mocked_get_now.return_value = \
            now.replace(year=now.year + contract_duration_years) + timedelta(days=contract_duration_days)
        for milestone in contract['milestones']:
            response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
                self.contract_id, milestone['id'], token), {'data': {
                    "amountPaid": {"amount": milestone['value']['amount']}, 'status': 'met'}})
            self.assertEqual(response.status, '200 OK')
            self.assertEqual(response.json['data']['status'], 'met')
            self.assertEqual(response.json['data']['amountPaid']['amount'], milestone['value']['amount'])

    # make sure that contract without non-terminated milestones
    # and contact.amountPaid.amount equal contract.value.amount
    contract = self.app.get('/contracts/{}'.format(self.contract['id'])).json['data']
    self.assertEqual(contract['amountPaid']['amount'], contract['value']['amount'])
    self.assertEqual(
        False,
        any(milestone['status'] in ['pending', 'scheduled'] for milestone in contract['milestones'])
    )

    # terminate contract without terminationDetails
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"status": "terminated"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'terminated')


def contract_patch_milestones_value_amount(self):
    tender_token = self.initial_data['tender_token']

    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    contract = response.json['data']

    response = self.app.patch_json('/contracts/{}/credentials?acc_token={}'.format(
        self.contract_id, tender_token), {'data': ''})
    self.assertEqual(response.status, '200 OK')
    token = response.json['access']['token']

    # Checking available changes
    self.assertEqual(contract.get('changes', []), [])

    # Create pending change
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract_id, token), {'data': {
            'rationale': u'причина зміни укр',
            'rationale_en': 'change cause en',
            'rationaleTypes': ['itemPriceVariation']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')
    change_id = response.json['data']['id']

    # Patch all visible milestones value.amount to 0
    for milestone in contract['milestones']:
        if milestone['value']['amount'] == 0:
            continue
        response = self.app.patch_json(
            '/contracts/{}/milestones/{}?acc_token={}'.format(self.contract_id, milestone['id'], token),
            {'data': {"value": {"amount": 0}}})
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.json['data']['value']['amount'], 0)

    # Close pending change via set change.status to active
    response = self.app.patch_json('/contracts/{}/changes/{}?acc_token={}'.format(self.contract_id, change_id, token),
                                  {'data': {'status': 'active', 'dateSigned': get_now().isoformat()}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'active')

    # Terminate all visible milestone to met
    now = get_now()
    # time travel to contract.period.endDate
    with patch('openprocurement.contracting.esco.validation.get_now') as mocked_get_now:
        contract_duration_years = self.initial_data['value']['contractDuration']['years']
        contract_duration_days = self.initial_data['value']['contractDuration']['days']
        mocked_get_now.return_value = \
            now.replace(year=now.year + contract_duration_years) + timedelta(days=contract_duration_days)
        for milestone in contract['milestones']:
            response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
                self.contract_id, milestone['id'], token), {'data': {
                    "amountPaid": {"amount": 0}, 'status': 'met'}})
            self.assertEqual(response.status, '200 OK')
            self.assertEqual(response.json['data']['status'], 'met')
            self.assertEqual(response.json['data']['amountPaid']['amount'], 0)

    # Check that all milestones terminated in met status
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']["status"], "active")
    for milestone in response.json['data']['milestones']:
        self.assertEqual(milestone['status'], 'met')
        self.assertEqual(milestone['value']['amount'], 0)
        self.assertEqual(milestone['amountPaid']['amount'], 0)

    # terminate contract without terminationDetails
    response = self.app.patch_json('/contracts/{}?acc_token={}'.format(
        self.contract['id'], token), {"data": {"status": "terminated"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'terminated')
    self.assertNotIn('terminationDetails', response.json['data'])
