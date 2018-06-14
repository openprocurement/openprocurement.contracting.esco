# -*- coding: utf-8 -*-
from datetime import timedelta
from iso8601 import parse_date
from openprocurement.api.utils import (
    get_now,
    raise_operation_error,
    update_logging_context,
)
from openprocurement.api.validation import validate_data
from openprocurement.contracting.esco.models import Milestone
from openprocurement.contracting.esco.constants import DAYS_PER_YEAR
from openprocurement.contracting.esco.utils import update_delta


# milestones
def validate_patch_milestone_data(request):
    return validate_data(request, Milestone, True)


def validate_milestones_sum_amount_paid(request):
    amountPaid = request.validated['data'].get('amountPaid', {}).get('amount', 0)
    contract = request.context.__parent__
    milestones_amountPaids = [milestone.amountPaid.amount for milestone in contract.milestones]
    if not sum(milestones_amountPaids) + amountPaid <= contract.value.amount:
        raise_operation_error(
            request, u"The sum of milestones amountPaid.amount can't be greater than contract.value.amount"
        )

def validate_milestone_status_change(request):
    milestone = request.context
    data = request.validated['data']
    # can't update status from scheduled and to scheduled and to spare:)
    if milestone.status != data['status'] and (milestone.status == 'scheduled' or
                                               data['status'] == 'scheduled' or
                                               data['status'] == 'spare'):
        raise_operation_error(request, "Can't update milestone to {} status".format(data['status']))


def validate_update_milestone_in_terminated_status(request):
    milestone = request.context
    if milestone.status in ['met', 'notMet', 'partiallyMet', 'spare']:
        raise_operation_error(request, "Can't update milestone in current ({}) status".format(milestone.status))


def validate_update_milestone_in_scheduled_status(request):
    milestone = request.context
    changes = milestone.__parent__.changes
    pending_change = True if len(changes) > 0 and changes[-1].status == 'pending' else False
    if not pending_change and milestone.status == 'scheduled':
        raise_operation_error(request, "Can't update milestone in scheduled status without pending change")


def validate_update_milestone_value(request):
    milestone = request.context
    changes = milestone.__parent__.changes
    pending_change = True if len(changes) > 0 and changes[-1].status == 'pending' else False
    if not pending_change and milestone.status in ['pending', 'scheduled']:
        value = request.validated['data']['value']
        for k in value.keys():
            v = getattr(milestone.value, k)
            if v != value[k]:
                raise_operation_error(request, "Contract doesn't have any change in 'pending' status.")


def validate_update_milestone_amountPaid(request):
    milestone = request.context
    if milestone.status == 'scheduled':
        amountPaid = request.validated['data']['amountPaid']
        for k in amountPaid.keys():
            v = getattr(milestone.amountPaid, k)
            if v != amountPaid[k]:
                raise_operation_error(request, "Can't update 'amountPaid' for scheduled milestone")


def validate_pending_milestone_update_period(request):
    milestone = request.context
    if milestone.status == 'pending' and milestone.period.startDate > get_now():
        raise_operation_error(request, "Can't update milestone before period.startDate")


def validate_terminate_contract_amount_paid(request):
    data = request.validated['data']
    contract = request.context
    if data['status'] != 'active' and contract['value']['amount'] != contract['amountPaid']['amount'] and \
            not data['terminationDetails']:
        raise_operation_error(request, "terminationDetails is required.")


# milestone documents
def validate_terminated_milestone_document_operation(request):
    # data check allows use same validator function for put, patch and post
    if 'data' in request.validated:
        data = request.validated['data']
        # for DS patch/put - get all requeired info
        if not "relatedItem" in data and "relatedItem" in request.context:
            data['relatedItem'] = request.context['relatedItem']
        if 'documentOf' in request.context and request.context['documentOf'] == 'milestone':
            data['documentOf'] = request.context['documentOf']
    else:
        data = request.context
    if "relatedItem" in data and data.get('documentOf') == 'milestone':
        for m in request.validated['contract'].milestones:
            if m.id == data['relatedItem'] and m.status in ['met', 'notMet', 'partiallyMet', 'spare']:
                raise_operation_error(request, "Can't {} document in current ({}) milestone status".format(
                    'update' if request.method == 'PUT' else 'add', m.status))


def validate_scheduled_milestone_document_operation(request):
    # data check allows use same validator function for put, patch and post
    if 'data' in request.validated:
        data = request.validated['data']
        # for DS patch/put - get all requeired info
        if not "relatedItem" in data and "relatedItem" in request.context:
            data['relatedItem'] = request.context['relatedItem']
        if 'documentOf' in request.context and request.context['documentOf'] == 'milestone':
            data['documentOf'] = request.context['documentOf']
    else:
        data = request.context
    # in case of POST context is contract, so changes are in request.context
    # in case of PATCH or PUT context is document, so changes are in request.context.__parent__
    changes = request.context.changes if hasattr(request.context, 'changes') else \
        request.context.__parent__.changes
    pending_change = True if len(changes) > 0 and changes[-1].status == 'pending' else False
    if "relatedItem" in data and data.get('documentOf') == 'milestone':
        for m in request.validated['contract'].milestones:
            if m.id == data['relatedItem'] and m.status == 'scheduled' and not pending_change:
                raise_operation_error(request, "Can't {} document to scheduled milestone without pending change".format(
                    'update' if request.method == 'PUT' else 'add'))


def validate_update_contract_end_date(request):
    """
    Function suppose to validate contract.period.endDate(cPeD):
    - cPeD can be changed only if pending change exist
    - cPeD cannot be less than milestone-in-pending-status-startDate
    - contract duration cannot be over 15 years, so cPeD should be less than
      last-milestone-endDate
    If conditions are not met, exception is raised, client gets
     json['data']['errors'] with error description.
    
    :param request
    :return: None
    :rtype: None
    """
    if 'period' in request.validated['data']:
        contract_period_end_date = parse_date(request.validated['data']['period']['endDate'])
        if request.context.period.endDate != contract_period_end_date:
            contract = request.context

            changes = contract.changes
            pending_change = True if len(changes) > 0 and changes[-1].status == 'pending' else False

            if not pending_change:
                raise_operation_error(request, "Can't update endDate of contract without pending change")

            pending_milestones = [x for x in contract.milestones if
                                  x.status == 'pending']
            if len(pending_milestones) != 1:
                raise_operation_error(request, "Can't update contract endDate, "
                                               "all milestones are in terminated statuses")

            if contract_period_end_date < pending_milestones[0].period.startDate:
                raise_operation_error(request, "Can't update contract endDate, if "
                                     "it is less than pending milestone startDate")

            delta = timedelta(days=DAYS_PER_YEAR * 15)
            delta = update_delta(delta, contract)
            contract_max_end_date = contract.period.startDate + delta
            if contract_period_end_date > contract_max_end_date:
                raise_operation_error(request, "Contract period cannot be over 15 years")


def validate_update_contract_start_date(request):
    if 'period' in request.validated['data'] and \
            request.validated['data']['period']['startDate'] != request.context.period.startDate.isoformat():
        raise_operation_error(request, "Can't change startDate of contract")
