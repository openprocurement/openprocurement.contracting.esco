# -*- coding: utf-8 -*-
import os
from decimal import Decimal
from copy import deepcopy
from pytz import timezone
from iso8601 import parse_date
from datetime import datetime, timedelta
from uuid import uuid4
from cornice.resource import resource
from functools import partial

from openprocurement.api.traversal import get_item
from openprocurement.api.utils import error_handler
from openprocurement.contracting.api.traversal import Root
from openprocurement.contracting.esco.constants import ACCELERATOR_RE, DAYS_PER_YEAR

from esculator.calculations import discount_rate_days, payments_days, calculate_payments

def factory(request):
    request.validated['contract_src'] = {}
    root = Root(request)
    if not request.matchdict or not request.matchdict.get('contract_id'):
        return root
    request.validated['contract_id'] = request.matchdict['contract_id']
    contract = request.contract
    contract.__parent__ = root
    request.validated['contract'] = request.validated['db_doc'] = contract
    if request.method != 'GET':
        request.validated['contract_src'] = contract.serialize('plain')
    if request.matchdict.get('milestone_id'):
        return get_item(contract, 'milestone', request)
    request.validated['id'] = request.matchdict['contract_id']
    return contract


milestoneresource = partial(
    resource,
    error_handler=error_handler,
    factory=factory
)

TZ = timezone(os.environ['TZ'] if 'TZ' in os.environ else 'Europe/Kiev')


def to_decimal(fraction):
    return str(Decimal(fraction.numerator) / Decimal(fraction.denominator))


def generate_milestones(contract):
    accelerator = 0
    if 'procurementMethodDetails' in contract:
        re_obj = ACCELERATOR_RE.search(contract['procurementMethodDetails'])
        if re_obj and 'accelerator' in re_obj.groupdict():
            accelerator = int(re_obj.groupdict()['accelerator'])

    npv_calculation_duration = 20
    announcement_date = parse_date(contract['noticePublicationDate'])

    contract_days = timedelta(days=contract['value']['contractDuration']['days'])
    contract_years = timedelta(days=contract['value']['contractDuration']['years'] * DAYS_PER_YEAR)
    date_signed = parse_date(contract['dateSigned'])
    signed_delta = date_signed - announcement_date
    if 'period' not in contract or ('mode' in contract and contract['mode'] == 'test'):
        contract_end_date = announcement_date + contract_years + contract_days
        if accelerator:
            real_date_signed = announcement_date + timedelta(seconds=signed_delta.total_seconds() * accelerator)
            contract['dateSigned'] = real_date_signed.isoformat()

        contract['period'] = {
            'startDate': contract['dateSigned'],
            'endDate': contract_end_date.isoformat()
        }

    # set contract.period.startDate to contract.dateSigned if missed
    if 'startDate' not in contract['period']:
        contract['period']['startDate'] = contract['dateSigned']

    contract_start_date = parse_date(contract['period']['startDate'])
    contract_end_date = parse_date(contract['period']['endDate'])

    contract_duration_years = contract['value']['contractDuration']['years']
    contract_duration_days = contract['value']['contractDuration']['days']
    yearly_payments_percentage = contract['value']['yearlyPaymentsPercentage']
    annual_cost_reduction = contract['value']['annualCostsReduction']

    days_for_discount_rate = discount_rate_days(announcement_date, DAYS_PER_YEAR, npv_calculation_duration)
    days_with_payments = payments_days(
        contract_duration_years, contract_duration_days, days_for_discount_rate, DAYS_PER_YEAR,
        npv_calculation_duration
    )

    payments = calculate_payments(
        yearly_payments_percentage, annual_cost_reduction, days_with_payments, days_for_discount_rate
    )

    milestones = []
    years_before_contract_start = contract_start_date.year - announcement_date.year

    last_milestone_sequence_number = 16 + years_before_contract_start

    for sequence_number in xrange(1, last_milestone_sequence_number + 1):
        date_modified = datetime.now(TZ)
        milestone = {
            'id': uuid4().hex,
            'sequenceNumber': sequence_number,
            'date': date_modified.isoformat(),
            'dateModified': date_modified.isoformat(),
            'amountPaid': {
                "amount": 0,
                "currency": contract['value']['currency'],
                "valueAddedTaxIncluded": contract['value']['valueAddedTaxIncluded']
            },
            'value': {
                "amount": to_decimal(payments[sequence_number - 1]) if sequence_number <= 21 else 0.00,
                "currency": contract['value']['currency'],
                "valueAddedTaxIncluded": contract['value']['valueAddedTaxIncluded']
            },
        }

        if sequence_number == 1:
            milestone_start_date = announcement_date
            milestone_end_date = TZ.localize(datetime(announcement_date.year + sequence_number, 1, 1))
            milestone['status'] = 'pending'
        elif sequence_number == last_milestone_sequence_number:
            milestone_start_date = TZ.localize(datetime(announcement_date.year + sequence_number - 1, 1, 1))
            milestone_end_date = contract_start_date + timedelta(days=DAYS_PER_YEAR * 15)
        else:
            milestone_start_date = TZ.localize(datetime(announcement_date.year + sequence_number - 1, 1, 1))
            milestone_end_date = TZ.localize(datetime(announcement_date.year + sequence_number, 1, 1))

        if contract_end_date.year >= milestone_start_date.year and sequence_number != 1:
            milestone['status'] = 'scheduled'
        elif contract_end_date.year < milestone_start_date.year:
            milestone['status'] = 'spare'

        if contract_end_date.year == announcement_date.year + sequence_number - 1:
            milestone_end_date = contract_end_date

        milestone['period'] = {
            'startDate': milestone_start_date.isoformat(),
            'endDate': milestone_end_date.isoformat()
        }
        title = "Milestone #{} of year {}".format(sequence_number, milestone_start_date.year)
        milestone['title'] = title
        milestone['description'] = title
        milestones.append(milestone)
    if accelerator:
        accelerate_milestones(milestones, DAYS_PER_YEAR, accelerator)
        # restore accelerated contract.dateSigned

        contract['dateSigned'] = date_signed.isoformat()
        # accelerate contract.period.endDate
        delta = contract_days + contract_years
        contract_end_date = announcement_date + timedelta(seconds=delta.total_seconds() / accelerator)
        contract['period'] = {
            'startDate': contract['dateSigned'],
            'endDate': contract_end_date.isoformat()
        }
    return milestones


def accelerate_milestones(milestones, days_per_year, accelerator):
    year = timedelta(seconds=timedelta(days=days_per_year).total_seconds() / accelerator)
    previous_end_date = None
    for index, milestone in enumerate(milestones):
        if index == 0:
            start_date = parse_date(milestone['period']['startDate'])
            end_date = parse_date(milestone['period']['endDate'])
            delta = end_date - start_date
            end_date = start_date + timedelta(seconds=delta.total_seconds() / accelerator)

            milestone['period']['endDate'] = end_date.isoformat()
        elif milestone['status'] == 'spare' and milestones[index - 1]['status'] in tuple(['scheduled', 'pending']):
            previous_start_date = parse_date(milestones[index - 1]['period']['startDate'])
            previous_end_date = previous_start_date + year
            real_start_date = parse_date(milestone['period']['startDate'])
            end_date = parse_date(milestone['period']['endDate'])
            delta = end_date - real_start_date
            end_date = previous_end_date + timedelta(seconds=delta.total_seconds() / accelerator)

            milestone['period'] = {
                'startDate': previous_end_date.isoformat(),
                'endDate': end_date.isoformat()
            }
        else:
            real_start_date = parse_date(milestone['period']['startDate'])
            end_date = parse_date(milestone['period']['endDate'])

            milestone['period']['startDate'] = milestones[index - 1]['period']['endDate']

            start_date = parse_date(milestones[index - 1]['period']['endDate'])
            delta = end_date - real_start_date
            end_date = start_date + timedelta(seconds=delta.total_seconds() / accelerator)

            milestone['period']['endDate'] = end_date.isoformat()


def update_milestones_dates_and_statuses(request):
    """
    Update milestones endDates and statuses, due changed contract period
    endDate. Milestones are copied from request.validated['data']['milestones']
    If endDate is increased, some spare milestones need to be opened (status
    is changed to scheduled).
    If endDate is decreased, some scheduled milestones need to be changed to
    spare.

    :param request
    :return: None
    :rtype: None
    """
    contract = request.context
    new_contract_end_date = parse_date(request.validated['data']['period']['endDate'])
    milestones = request.context.milestones  # real milestones
    target_milestones = deepcopy(request.validated['contract_src']['milestones'])
    for number, m in enumerate(milestones):
        if m.status in ['met', 'notMet', 'partiallyMet']:
            continue
        # stretch milestone period endDate
        if m.period.startDate <= contract.period.endDate <= m.period.endDate:
            if number + 1 < len(milestones):
                target_milestones[number]['period']['endDate'] = \
                    milestones[number+1].period.startDate.isoformat()
            else:
                delta = timedelta(days=DAYS_PER_YEAR*15)
                delta = update_delta(delta, contract)
                target_milestones[number]['period']['endDate'] = (contract.period.startDate + delta).isoformat()
        # shrink milestone period endDate
        if target_milestones[number]['period']['startDate']\
                <= request.validated['data']['period']['endDate'] <=\
                target_milestones[number]['period']['endDate']:
            target_milestones[number]['period']['endDate'] = new_contract_end_date
        #  increase endDate, need open (spare-> scheduled) new milestones
        if new_contract_end_date > contract.period.endDate:
            if m.period.startDate <= new_contract_end_date:
                if m.status == 'spare':
                    target_milestones[number]['status'] = 'scheduled'
        #  decrease endDate need to hide (scheduled -> spare) milestones
        else:
            if m.period.endDate > new_contract_end_date:
                if m.status == 'scheduled':
                    target_milestones[number]['status'] = 'spare'
                if m.period.startDate <= new_contract_end_date:
                    if m.status != 'pending':
                        target_milestones[number]['status'] = 'scheduled'

    request.validated['data']['milestones'] = target_milestones


def update_delta(delta, contract):
    """
    Update delta, we need this function for testing. To shrink dates.

    :param delta
    :param contract
    :return: delta
    :rtype: timedelta
    """
    if 'procurementMethodDetails' in contract and contract.procurementMethodDetails:
            re_obj = ACCELERATOR_RE.search(contract.procurementMethodDetails)
            if re_obj and 'accelerator' in re_obj.groupdict():
                return timedelta(seconds=delta.total_seconds() / int(re_obj.groupdict()['accelerator']))
    return delta
