# -*- coding: utf-8 -*-
from datetime import timedelta

from munch import munchify

from openprocurement.api.utils import get_now
from openprocurement.contracting.esco.utils import update_delta


def listing_milestones(self):
    response = self.app.get('/contracts/{}/milestones'.format(self.contract['id']))
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    data = response.json['data']
    self.assertEqual(len(data), 8)
    sequenceNumber = 1
    for milestone in data:
        if sequenceNumber == 1:
            self.assertEqual(milestone['status'], 'pending')
        else:
            self.assertEqual(milestone['status'], 'scheduled')
        self.assertEqual(milestone['sequenceNumber'], sequenceNumber)
        sequenceNumber += 1


def get_milestone_by_id(self):
    milestone_id = self.initial_data['milestones'][1]['id']
    contract_id = self.contract['id']

    # Receive milestone by id
    response = self.app.get(
        '/contracts/{}/milestones/{}'.format(contract_id, milestone_id)
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    initial_milestone = self.initial_data['milestones'][1]
    milestone = response.json['data']
    self.assertEqual(set(milestone.keys()), {u'status', u'description', u'sequenceNumber', u'title', u'period',
                                             u'value', u'id', u'date', u'amountPaid', u'dateModified'})
    for key in initial_milestone.keys():
        # value.amount is special - it's decimal
        if key == 'value':
            self.assertEqual(round(float(initial_milestone[key]['amount']), 2), milestone[key]['amount'])
            self.assertEqual(initial_milestone[key]['currency'], milestone[key]['currency'])
            self.assertEqual(initial_milestone[key]['valueAddedTaxIncluded'], milestone[key]['valueAddedTaxIncluded'])
        else:
            self.assertEqual(initial_milestone[key], milestone[key])
    self.assertEqual(milestone['id'], milestone_id)
    self.assertEqual(milestone['status'], 'scheduled')
    self.assertEqual(
        milestone['amountPaid'],
        {'amount': 0, 'currency': 'UAH', 'valueAddedTaxIncluded': True}
    )
    self.assertIn('date', milestone)
    self.assertIn('dateModified', milestone)

    # Try get milestone in spare status
    milestone_id = self.initial_data['milestones'][9]['id']
    self.assertEqual(self.initial_data['milestones'][9]['status'], 'spare')
    response = self.app.get(
        '/contracts/{}/milestones/{}'.format(contract_id, milestone_id)
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertIs(response.json['data'], None)

    # Try receive milestone by invalid id
    response = self.app.get(
        '/contracts/{}/milestones/invalid_id'.format(contract_id),
        status=404
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '404 Not Found')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u'Not Found',
                u'location': u'url',
                u'name': u'milestone_id'
            }]
        }
    )


def patch_milestone_description(self):
    # Receive available milestones
    response = self.app.get('/contracts/{}/milestones'.format(self.contract['id']))
    milestones = response.json['data']

    pending_milestone = milestones[0]
    scheduled_milestone = milestones[-1]
    self.assertEqual(pending_milestone['status'], 'pending')
    self.assertEqual(scheduled_milestone['status'], 'scheduled')
    self.assertNotEqual(len(pending_milestone['description']), 0)
    self.assertNotEqual(len(scheduled_milestone['description']), 0)

    # Remove description in pending milestone
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'description': ""}}
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['description'], "")
    self.assertEqual(milestone['id'], pending_milestone['id'])

    # Set amountPaid.amount in pending milestone
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'amountPaid': {"amount": 123456}}}
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['amountPaid']['amount'], 123456)
    self.assertEqual(milestone['description'], "")
    self.assertEqual(milestone['id'], pending_milestone['id'])

    # Not allow switch milestone in one of terminated statuses (met, notMet and partiallyMet) if description empty
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'status': "met"}},
        status=422
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': [u"Description can't be empty in follow statuses (met, notMet, partiallyMet)"],
                u'location': u'body',
                u'name': u'status'
            }]
        }
    )

    # Successfull switch milestone in one of terminated statuses (met, notMet, partiallyMet)
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'status': "met", 'description': 'Milestone #1'}},
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['status'], 'met')
    self.assertEqual(milestone['description'], 'Milestone #1')
    self.assertEqual(milestone['amountPaid']['amount'], 123456)

    # Not allow change description in terminated milestones
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'description': 'New description of milestone #1'}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in current (met) status",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Not allow remove description in scheduled milestone without pending change
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], scheduled_milestone['id'], self.contract_token
        ),
        {'data': {'description': ""}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            "status": "error",
            "errors": [{
                "location": "body",
                "name": "data",
                "description": "Can't update milestone in scheduled status without pending change"
            }]
        }
    )

    # Not allow change milestone description in spare status
    spare_milestone_id = self.initial_data['milestones'][-1]['id']
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], spare_milestone_id, self.contract_token
        ),
        {'data': {'description': ""}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            "status": "error",
            "errors": [{
                "location": "body",
                "name": "data",
                "description": "Can't update milestone in current (spare) status"
            }]
        }
    )

    # Change description with pending change
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract_id, self.contract_token), {'data': {
            'rationale': u'причина зміни укр',
            'rationale_en': 'change cause en',
            'rationaleTypes': ['itemPriceVariation']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')

    # Not allow change milestone description in spare status with pending change
    spare_milestone_id = self.initial_data['milestones'][-1]['id']
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], spare_milestone_id, self.contract_token
        ),
        {'data': {'description': ""}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            "status": "error",
            "errors": [{
                "location": "body",
                "name": "data",
                "description": "Can't update milestone in current (spare) status"
            }]
        }
    )

    # Not allow change description in terminated milestones with pending change
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'description': 'New description of milestone #1'}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in current (met) status",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Get scheduled milestone
    response = self.app.get('/contracts/{}/milestones/{}'.format(self.contract['id'], scheduled_milestone['id']))
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['id'], scheduled_milestone['id'])
    self.assertEqual(response.json['data']['status'], 'scheduled')
    self.assertNotEqual(response.json['data']['description'], 'New description of milestone #scheduled')

    # Allow change description in scheduled milestone with pending change
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], scheduled_milestone['id'], self.contract_token
        ),
        {'data': {'description': 'New description of milestone #scheduled'}},
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['description'], 'New description of milestone #scheduled')


def patch_milestone_title(self):
    # Receive available milestones
    response = self.app.get('/contracts/{}/milestones'.format(self.contract['id']))
    milestones = response.json['data']

    pending_milestone = milestones[0]
    scheduled_milestone = milestones[-1]
    self.assertEqual(pending_milestone['status'], 'pending')
    self.assertEqual(scheduled_milestone['status'], 'scheduled')
    self.assertNotEqual(len(pending_milestone['title']), 0)
    self.assertNotEqual(len(scheduled_milestone['title']), 0)

    # Remove title in pending milestone
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'title': ""}}
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['title'], "")
    self.assertEqual(milestone['id'], pending_milestone['id'])

    # Set amountPaid.amount in pending milestone
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'amountPaid': {"amount": 123456}}}
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['amountPaid']['amount'], 123456)
    self.assertEqual(milestone['title'], "")
    self.assertEqual(milestone['id'], pending_milestone['id'])

    # Not allow switch milestone in one of terminated statuses (met, notMet and partiallyMet) if title empty
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'status': "met"}},
        status=422
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': [u"Title can't be empty in follow statuses (met, notMet, partiallyMet)"],
                u'location': u'body',
                u'name': u'status'
            }]
        }
    )

    # Successfull switch milestone in one of terminated statuses (met, notMet, partiallyMet)
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'status': "met", 'title': 'Milestone #1'}},
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['status'], 'met')
    self.assertEqual(milestone['title'], 'Milestone #1')
    self.assertEqual(milestone['amountPaid']['amount'], 123456)

    # Not allow change title in terminated milestones
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'title': 'New title of milestone #1'}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in current (met) status",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Not allow remove title in scheduled milestone without pending change
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], scheduled_milestone['id'], self.contract_token
        ),
        {'data': {'title': ""}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            "status": "error",
            "errors": [{
                "location": "body",
                "name": "data",
                "description": "Can't update milestone in scheduled status without pending change"
            }]
        }
    )

    # Not allow change milestone title in spare status
    spare_milestone_id = self.initial_data['milestones'][-1]['id']
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], spare_milestone_id, self.contract_token
        ),
        {'data': {'title': ""}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            "status": "error",
            "errors": [{
                "location": "body",
                "name": "data",
                "description": "Can't update milestone in current (spare) status"
            }]
        }
    )

    # Change title with pending change
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract_id, self.contract_token), {'data': {
            'rationale': u'причина зміни укр',
            'rationale_en': 'change cause en',
            'rationaleTypes': ['itemPriceVariation']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')

    # Not allow change milestone title in spare status with pending change
    spare_milestone_id = self.initial_data['milestones'][-1]['id']
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], spare_milestone_id, self.contract_token
        ),
        {'data': {'title': ""}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            "status": "error",
            "errors": [{
                "location": "body",
                "name": "data",
                "description": "Can't update milestone in current (spare) status"
            }]
        }
    )

    # Not allow change title in terminated milestones with pending change
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], pending_milestone['id'], self.contract_token
        ),
        {'data': {'title': 'New title of milestone #1'}},
        status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in current (met) status",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Get scheduled milestone
    response = self.app.get('/contracts/{}/milestones/{}'.format(self.contract['id'], scheduled_milestone['id']))
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['id'], scheduled_milestone['id'])
    self.assertEqual(response.json['data']['status'], 'scheduled')
    self.assertNotEqual(response.json['data']['title'], 'New title of milestone #scheduled')

    # Allow change title in scheduled milestone with pending change
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(
            self.contract['id'], scheduled_milestone['id'], self.contract_token
        ),
        {'data': {'title': 'New title of milestone #scheduled'}},
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['title'], 'New title of milestone #scheduled')


def patch_milestones_status_change(self):
    scheduled_milestone_id = self.initial_data['milestones'][2]['id']
    pending_milestone_id = self.initial_data['milestones'][0]['id']
    contract_id = self.contract['id']
    data = {'amountPaid': {'amount': 500000}}

    # Not allow change milestone in scheduled status
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, scheduled_milestone_id, self.contract_token),
        {'data': data}, status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in scheduled status without pending change",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Not allow patch milestone status scheduled -> spare
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, scheduled_milestone_id, self.contract_token),
        {"data": {"status": "spare"}}, status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone to spare status",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Not allow patch milestone status pending -> spare
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, pending_milestone_id, self.contract_token),
        {"data": {"status": "spare"}}, status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            "status": "error",
            "errors": [{
                "location": "body",
                "name": "data",
                "description": "Can't update milestone to spare status"
            }]
        }
    )

    # Patch first pending milestone only amountPaid.amount and check changing only dateModified of milestone
    start_dateModified = self.initial_data['milestones'][0]['dateModified']
    start_date = self.initial_data['milestones'][0]['date']
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, pending_milestone_id, self.contract_token),
        {'data': data}
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['status'], 'pending')
    self.assertEqual(milestone['amountPaid']['amount'], data['amountPaid']['amount'])
    self.assertEqual(milestone['date'], start_date)
    self.assertGreater(milestone['dateModified'], start_dateModified)

    # Don't allow change period
    many_days = timedelta(days=2000)
    many_days = update_delta(many_days, munchify(self.initial_data))
    end_date = (get_now() + many_days).isoformat()

    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, pending_milestone_id, self.contract_token),
        {'data': {'period': {'endDate': end_date}}},
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertIs(response.json, None)

    response = self.app.get('/contracts/{}/milestones/{}'.format(contract_id, pending_milestone_id))
    milestone = response.json['data']
    self.assertNotEqual(end_date, milestone['period']['endDate'])
    self.assertEqual(milestone['period'], self.initial_data['milestones'][0]['period'])

    # Don't allow update milestone amountPaid.amount if sum of all milesones amountPaid.amount
    # greater than contract.value.amount
    data['amountPaid']['amount'] = float(self.initial_data['milestones'][1]['value']['amount']) + 10000000
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, pending_milestone_id, self.contract_token),
        {'data': data}, status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"The sum of milestones amountPaid.amount can't be greater than contract.value.amount",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Patch second time first pending milestone amountPaid.amount and status and check changing date and dateModified
    data['amountPaid']['amount'] = float(self.initial_data['milestones'][0]['value']['amount'])
    data['status'] = 'met'
    start_date = milestone['date']
    start_dateModified = milestone['dateModified']
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, pending_milestone_id, self.contract_token),
        {'data': data}
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['status'], data['status'])
    self.assertEqual(milestone['amountPaid']['amount'], data['amountPaid']['amount'])
    self.assertGreater(milestone['date'], start_date)
    self.assertGreater(milestone['dateModified'], start_dateModified)

    current_milestone_sequenceNumber = milestone['sequenceNumber']
    current_milestone_date = milestone['date']
    current_milestone_dateModified = milestone['dateModified']

    # Not allow patch milestone status met -> spare
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, pending_milestone_id, self.contract_token),
        {"data": {"status": "spare"}}, status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in current (met) status",
                u'location': u'body', u'name': u'data'
            }]
        }
    )

    # Check status next milestone and check date and dateModified must be equal to current milestone
    next_milestone_id = self.initial_data['milestones'][1]['id']
    response = self.app.get('/contracts/{}/milestones/{}'.format(contract_id, next_milestone_id))
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    next_milestone_sequenceNumber = milestone['sequenceNumber']
    self.assertEqual(milestone['amountPaid']['amount'], 0)
    self.assertEqual(milestone['status'], 'pending')
    self.assertEqual(milestone['date'], current_milestone_date)
    self.assertEqual(milestone['dateModified'], current_milestone_dateModified)
    self.assertGreater(next_milestone_sequenceNumber, current_milestone_sequenceNumber)


    # Don't allow change milestone in one of terminated statuses (notMet, met, partiallyMet)
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, pending_milestone_id, self.contract_token),
        {'data': data}, status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in current (met) status",
                u'location': u'body', u'name': u'data'
            }]
        }
    )

    # Don't allow set notMet status for milestone if amountPaid.amount greater than 0
    data['status'] = 'notMet'
    data['amountPaid']['amount'] = float(self.initial_data['milestones'][1]['value']['amount']) - 10000
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, next_milestone_id, self.contract_token),
        {'data': data}, status=422
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': [u"Milestone can't be in status 'notMet' if amountPaid.amount greater than 0"],
                u'location': u'body',
                u'name': u'status'
            }]
        }
    )

    # Don't allow set partiallyMet status for milestone if amountPaid.amount is greater than milestone.value.amount
    data['status'] = 'partiallyMet'
    data['amountPaid']['amount'] = float(self.initial_data['milestones'][1]['value']['amount']) + 10000
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, next_milestone_id, self.contract_token),
        {'data': data}, status=422
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': [u"Milestone can't be in status 'partiallyMet' if amountPaid.amount not greater then 0 "
                                 "or not less value.amount"],
                u'location': u'body',
                u'name': u'status'
            }]
        }
    )

    if 'mode' in self.initial_data and self.initial_data['mode'] == u'test':
        #  make second milestone notMet, because when mode==test, cant change 2 milestone, now-time came
        contract = self.db.get(self.contract['id'])

        milestone_id = contract['milestones'][2]['id']
        milestone_period = contract['milestones'][2]['period']
        from copy import deepcopy
        contract['milestones'][2] = deepcopy(contract['milestones'][1])

        contract['milestones'][1]['status'] = u'notMet'
        contract['milestones'][2]['id'] = milestone_id
        contract['milestones'][2]['period'] = milestone_period

        self.db.save(contract)
        next_milestone_id = milestone_id

    # Try to update pending milestone before it's period
    data['status'] = 'met'
    data['amountPaid']['amount'] = float(self.initial_data['milestones'][1]['value']['amount'])
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, next_milestone_id, self.contract_token),
        {'data': data}, status=403
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone before period.startDate",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Don't allow set met status if amountPaid.amount less than value.amount
    del data['amountPaid']
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, next_milestone_id, self.contract_token),
        {'data': data}, status=422
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': [u"Milestone can't be in status 'met' if amountPaid.amount less than value.amount"],
                u'location': u'body',
                u'name': u'status'
            }]

        }
    )

    # SPARE milestone
    # Not allows any action with milestone in spare status via patch
    spare_milestone = self.initial_data['milestones'][-2]
    self.assertEqual(spare_milestone['status'], 'spare')

    # try get spare milestone
    response = self.app.get(
        '/contracts/{}/milestones/{}'.format(contract_id, spare_milestone['id'])
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertIs(response.json['data'], None)

    # Not allow patch milestone from spare status to another
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, spare_milestone['id'], self.contract_token),
        {"data": {"status": "pending"}}, status=403
    )
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in current (spare) status",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )

    # Not allow patch milestone in spare status
    response = self.app.patch_json(
        '/contracts/{}/milestones/{}?acc_token={}'.format(contract_id, spare_milestone['id'], self.contract_token),
        {"data": {"amountPaid": {"amount": 123450}}}, status=403
    )
    self.assertEqual(
        response.json,
        {
            u'status': u'error',
            u'errors': [{
                u'description': u"Can't update milestone in current (spare) status",
                u'location': u'body',
                u'name': u'data'
            }]
        }
    )


def pending_status_update(self):
    # status update for PENDING milestone
    # get correct pending milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]
    # make sure it's pending milestone!
    self.assertEqual(milestone['status'], 'pending')

    # patch pending -> scheduled is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "scheduled"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone to scheduled status"}])

    # pending to pending gives nothing
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "pending"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}/milestones/{}'.format(self.contract_id, milestone['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    # current pending milestone
    self.assertEqual(milestone, response.json['data'])

    # pending to pending (with value) works as expected - needs pending change
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"amount": 700000},
            "status": "pending"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Contract doesn't have any change in 'pending' status."}])

    # pending to met is allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            'status': 'met',
            'amountPaid': {'amount': milestone['value']['amount']}}}
    )
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    milestone = response.json['data']
    self.assertEqual(milestone['status'], 'met')
    self.assertEqual(milestone['amountPaid']['amount'], milestone['value']['amount'])


def scheduled_status_update(self):
    # status update for SCHEDULED milestone
    # get correct scheduled milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][1]
    # make sure it's scheduled milestone!
    self.assertEqual(milestone['status'], 'scheduled')

    # patch scheduled -> pending is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "pending"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone to pending status"}])

    # scheduled to scheduled  without change
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "scheduled"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data",
         "description": "Can't update milestone in scheduled status without pending change"}])

    # scheduled to scheduled (with amountPaid) works as expected - not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "amountPaid": {"amount": 700000},
            "status": "scheduled"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data",
         "description": "Can't update milestone in scheduled status without pending change"}])

    # even after creating change
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract_id, self.contract_token), {'data': {
            'rationale': u'причина зміни укр',
            'rationale_en': 'change cause en',
            'rationaleTypes': ['itemPriceVariation']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')

    # scheduled to scheduled with change gives nothing
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "scheduled"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}/milestones/{}'.format(self.contract_id, milestone['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    # current scheduled milestone
    self.assertEqual(milestone, response.json['data'])

    # update of amountPaid is still not allowed - at all
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "amountPaid": {"amount": 700000}},
            "status": "scheduled"}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update 'amountPaid' for scheduled milestone"}])

    # change value.amount
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"amount": 1000000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')

    # patch scheduled -> terminated status is not allowed
    # amountPaid equal value
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "met",
            "amountPaid": {"amount": 1000000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone to met status"}])

    # amountPaid less than value
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "partiallyMet",
            "amountPaid": {"amount": 1000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone to partiallyMet status"}])

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "notMet"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone to notMet status"}])


def met_status_update(self):
    # status update for MET milestone
    # make correct met milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]
    self.assertEqual(milestone['status'], 'pending')

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "met",
            "amountPaid": {"amount": 100000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']
    self.assertEqual(milestone['status'], 'met')

    # patch met status -> pending is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "pending"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (met) status"}])

    # patch met status -> scheduled is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "scheduled"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (met) status"}])

    # patch met status -> partiallyMet is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "partiallyMet"}}, status=422)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "status",
         "description": ["Milestone can't be in status 'partiallyMet' if amountPaid.amount not greater then 0 or not less value.amount"]}])

    # patch met status -> notMet is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "notMet"}}, status=422)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "status",
         "description": ["Milestone can't be in status 'notMet' if amountPaid.amount greater than 0"]}])


def notMet_status_update(self):
    # status update for NOT MET milestone
    # make correct notMet milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]
    self.assertEqual(milestone['status'], 'pending')

    # change value
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract_id, self.contract_token), {'data': {
            'rationale': u'причина зміни укр',
            'rationale_en': 'change cause en',
            'rationaleTypes': ['itemPriceVariation']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"amount": 1000000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "notMet"}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']
    self.assertEqual(milestone['status'], 'notMet')

    # patch notMet -> pending is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "pending"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (notMet) status"}])

    # pacth notMet -> scheduled is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "scheduled"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (notMet) status"}])

    # pacth notMet -> met is not allowed
    # amountPaid - more then value
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "met",
            "amountPaid": {"amount": 10000001}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (notMet) status"}])

    # patch notMet -> partiallyMet is not allowed
    # amountPaid - less then value
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "partiallyMet",
            "amountPaid": {"amount": 10000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (notMet) status"}])


def partiallyMet_status_update(self):
    # status update for PARTIALLY MET milestone
    # get correct pending milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]
    # make sure it's pending milestone!
    self.assertEqual(milestone['status'], 'pending')

    # change value
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract_id, self.contract_token), {'data': {
            'rationale': u'причина зміни укр',
            'rationale_en': 'change cause en',
            'rationaleTypes': ['itemPriceVariation']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"amount": 1000000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')

    # make it partiallyMet
    # amountPaid - less then value
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "partiallyMet",
            "amountPaid": {"amount": 10000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']
    self.assertEqual(milestone['status'], 'partiallyMet')

    # patch partiallyMet -> pending is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "pending"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (partiallyMet) status"}])

    # pacth partiallyMet -> scheduled is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "scheduled"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (partiallyMet) status"}])

    # pacth partiallyMet -> notMet is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "notMet"}}, status=422)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "status",
         "description": ["Milestone can't be in status 'notMet' if amountPaid.amount greater than 0"]}])

    # patch partiallyMet -> met is not allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "met"}}, status=422)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '422 Unprocessable Entity')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "status",
         "description": ["Milestone can't be in status 'met' if amountPaid.amount less than value.amount"]}])


def patch_milestone(self):
    # pending milestone updates
    # get correct pending milestone
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][0]
    # make sure it's pending milestone!
    self.assertEqual(milestone['status'], 'pending')

    # update of title, description, amountPaid is allowed w\o pending change
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "pending",
            "title": "new title",
            "description": "new description",
            "amountPaid": {"amount": 500000}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json["data"]["title"], "new title")
    self.assertEqual(response.json["data"]["description"], "new description")
    self.assertEqual(response.json["data"]["amountPaid"]["amount"], 500000)

    # can't update amountPaind currency and vat
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "amountPaid": {"currency": "USD", "valueAddedTaxIncluded": False}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    # self.assertGreater(response.json['data']['amountPaid']['amount'], self.initial_data['amountPaid']['amount'])
    self.assertEqual(response.json["data"]["amountPaid"]["amount"], 500000)

    response = self.app.get('/contracts/{}/milestones/{}'.format(self.contract_id, milestone['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json["data"]["amountPaid"]["currency"],
                     self.initial_data['milestones'][0]['amountPaid']['currency'])
    self.assertEqual(response.json["data"]["amountPaid"]["valueAddedTaxIncluded"],
                     self.initial_data['milestones'][0]['amountPaid']['valueAddedTaxIncluded'])

    # update of value is not allowed w/o pending change
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"amount": 700000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Contract doesn't have any change in 'pending' status."}])

    # create pending change
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract_id, self.contract_token), {'data': {
            'rationale': u'причина зміни укр',
            'rationale_en': 'change cause en',
            'rationaleTypes': ['itemPriceVariation']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    change = response.json['data']
    self.assertEqual(change['status'], 'pending')

    # now update of value is allowed
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"amount": 700000}}})
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json["data"]["value"]["amount"], 700000)

    # can't update value currency and vat
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"currency": "USD", "valueAddedTaxIncluded": False}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.body, 'null')

    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertGreater(response.json['data']['value']['amount'], self.initial_data['value']['amount'])

    response = self.app.get('/contracts/{}/milestones/{}'.format(self.contract_id, milestone['id']))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json["data"]["value"]["currency"],
                     self.initial_data['milestones'][0]['value']['currency'])
    self.assertEqual(response.json["data"]["value"]["valueAddedTaxIncluded"],
                     self.initial_data['milestones'][0]['value']['valueAddedTaxIncluded'])

    # activate change - now there is no pending changes
    response = self.app.patch_json('/contracts/{}/changes/{}?acc_token={}'.format(
        self.contract['id'], change['id'], self.contract_token), {'data': {
            'status': 'active',
            'dateSigned': get_now().isoformat()}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'active')

    # terminated milestone updates
    # set milestone's status to terminal - partiallyMet for example
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "partiallyMet"}})
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.json['data']['status'], 'partiallyMet')

    # update of title, description, amountPaid, value is forbidden
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"amount": 800000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (partiallyMet) status"}])

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "amountPaid": {"amount": 600000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (partiallyMet) status"}])

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "title": "new new",
            "description": "new new new"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update milestone in current (partiallyMet) status"}])

    # scheduled milestone updates
    # get correct scheduled milestone - third one
    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    milestone = response.json['data']['milestones'][2]
    # make sure it's scheduled milestone!
    self.assertEqual(milestone['status'], 'scheduled')

    # update of title/description, value, amountPaid is not allowed w/o pending change
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "status": "scheduled",
            "title": "new new",
            "description": "new new new"}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data",
         "description": "Can't update milestone in scheduled status without pending change"}])

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "value": {"amount": 700000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data",
         "description": "Can't update milestone in scheduled status without pending change"}])

    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "amountPaid": {"amount": 700000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data",
         "description": "Can't update milestone in scheduled status without pending change"}])

    # create pending change
    response = self.app.post_json('/contracts/{}/changes?acc_token={}'.format(
        self.contract_id, self.contract_token), {'data': {
            'rationale': u'причина зміни укр',
            'rationale_en': 'change cause en',
            'rationaleTypes': ['itemPriceVariation']}})
    self.assertEqual(response.status, '201 Created')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json['data']['status'], 'pending')

    # update of amountPaid is still not allowed - at all
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "amountPaid": {"amount": 700000}}}, status=403)
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.status, '403 Forbidden')
    self.assertEqual(response.json['errors'], [
        {"location": "body", "name": "data", "description": "Can't update 'amountPaid' for scheduled milestone"}])

    # update of title, description, value is allowed with pending change
    response = self.app.patch_json('/contracts/{}/milestones/{}?acc_token={}'.format(
        self.contract_id, milestone['id'], self.contract_token), {'data': {
            "title": "new title",
            "status": "scheduled",
            "description": "new description",
            "value": {"amount": 500000, "currency": "USD"}}})
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertEqual(response.json["data"]["title"], "new title")
    self.assertEqual(response.json["data"]["description"], "new description")
    self.assertEqual(response.json["data"]["value"]["amount"], 500000)
    self.assertEqual(response.json["data"]["value"]["currency"],
                     self.initial_data['milestones'][2]['value']['currency'])

    response = self.app.get('/contracts/{}'.format(self.contract_id))
    self.assertEqual(response.status, '200 OK')
    self.assertEqual(response.content_type, 'application/json')
    self.assertGreater(response.json['data']['value']['amount'], self.initial_data['value']['amount'])
