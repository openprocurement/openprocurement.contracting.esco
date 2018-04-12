# -*- coding: utf-8 -*-
from uuid import uuid4
from zope.interface import implementer
from schematics.exceptions import ValidationError
from schematics.transforms import whitelist, blacklist
from schematics.types import StringType, FloatType, IntType, MD5Type
from schematics.types.compound import ModelType
from schematics.types.serializable import serializable
from openprocurement.contracting.core.models import (
    IContract, IsoDateTimeType,
    Contract as BaseContract, Document as BaseDocument
)
from openprocurement.api.utils import get_now
from openprocurement.api.models import (
    plain_role, schematics_default_role,
    Value, Period, Model, ListType, DecimalType
)
from openprocurement.contracting.core.models import (
    contract_create_role as base_contract_create_role, contract_edit_role as base_contract_edit_role,
    contract_view_role, contract_administrator_role
)
from openprocurement.tender.esco.models import (
    ESCOValue as BaseESCOValue, to_decimal
)
from esculator import escp, npv


contract_create_role = base_contract_create_role + \
    whitelist('NBUdiscountRate', 'noticePublicationDate', 'yearlyPaymentsPercentageRange', 'minValue', 'milestones')
contract_edit_role = base_contract_edit_role + whitelist('milestones')


class IESCOContract(IContract):
    """ ESCO Contract marker interface """


class ESCOValue(BaseESCOValue):

    def validate_yearlyPaymentsPercentage(self, data, value):
        pass

    @serializable(serialized_name='amountPerformance', type=DecimalType(precision=-2))
    def amountPerformance_npv(self):
        """ Calculated energy service contract performance indicator """
        return to_decimal(npv(
            self.contractDuration.years,
            self.contractDuration.days,
            self.yearlyPaymentsPercentage,
            self.annualCostsReduction,
            self.__parent__.noticePublicationDate,
            self.__parent__.NBUdiscountRate))

    @serializable(serialized_name='amount', type=DecimalType(precision=-2))
    def amount_escp(self):
        return to_decimal(escp(
            self.contractDuration.years,
            self.contractDuration.days,
            self.yearlyPaymentsPercentage,
            self.annualCostsReduction,
            self.__parent__.noticePublicationDate))


class Document(BaseDocument):
    """ Contract Document """

    documentOf = StringType(
        required=True,
        choices=['tender', 'item', 'lot', 'contract', 'change', 'milestone'],
        default='contract'
    )

    def validate_relatedItem(self, data, relatedItem):
            if not relatedItem and \
                    data.get('documentOf') in ['item', 'change', 'milestone']:
                raise ValidationError(u'This field is required.')
            if relatedItem and isinstance(data['__parent__'], Model):
                contract = get_contract(data['__parent__'])
                if data.get('documentOf') == 'change' and \
                        relatedItem not in [i.id for i in contract.changes]:
                    raise ValidationError(
                        u"relatedItem should be one of changes"
                    )
                if data.get('documentOf') == 'item' and \
                        relatedItem not in [i.id for i in contract.items]:
                    raise ValidationError(
                        u"relatedItem should be one of items"
                    )
                if data.get('documentOf') == 'milestone' and \
                        relatedItem not in [i.id for i in contract.milesones]:
                    raise ValidationError(
                        u"relatedItem should be one of milestones"
                    )


class Milestone(Model):
    """ Contract Milestone """

    id = MD5Type(required=True, default=lambda: uuid4().hex)
    date = IsoDateTimeType()
    dateModified = IsoDateTimeType()
    description = StringType()
    period = ModelType(Period)
    sequenceNumber = IntType(required=True)
    status = StringType(
        required=True,
        choices=['scheduled', 'met', 'notMet', 'partiallyMet', 'pending'],
        default='scheduled'
    )
    value = ModelType(Value, required=True)
    amountPaid = ModelType(
        Value,
        default={'amount': 0, 'currency': 'UAH', 'valueAddedTaxIncluded': True}
    )
    title = StringType()

    class Options:
        roles = {
            'view': schematics_default_role,
            'edit': whitelist('status', 'amountPaid', 'value', 'title', 'description')
        }

    def validate_status(self, data, status):
        if status == 'met' and not data['amountPaid'].amount >= data['value'].amount:
            raise ValidationError(u"Milestone can't be in status 'met' if amountPaid.amount less than value.amount")
        elif status == 'notMet' and data['amountPaid'].amount > 0:
            raise ValidationError(u"Milestone can't be in status 'notMet' if amountPaid.amount greater than 0")
        elif status == 'partiallyMet' and not 0 < data['amountPaid'].amount < data['value'].amount:
            raise ValidationError(
                u"Milestone can't be in status 'partiallyMet' if amountPaid.amount not greater then 0 "
                "or not less value.amount"
            )


@implementer(IESCOContract)
class Contract(BaseContract):
    """ ESCO Contract """

    contractType = StringType(default='esco')
    fundingKind = StringType(choices=['budget', 'other'], default='other')
    milestones = ListType(ModelType(Milestone), default=list())
    minValue = ModelType(Value, required=True)
    NBUdiscountRate = FloatType(required=True, min_value=0, max_value=0.99)
    noticePublicationDate = IsoDateTimeType()
    value = ModelType(ESCOValue)
    yearlyPaymentsPercentageRange = FloatType(required=True)

    class Options:
        roles = {
            'plain': plain_role,
            'create': contract_create_role,
            'edit_active': contract_edit_role,
            'edit_terminated': whitelist(),
            'view': contract_view_role + whitelist('NBUdiscountRate', 'contractType', 'milestones'),
            'Administrator': contract_administrator_role,
            'default': schematics_default_role,
        }

    @serializable(serialized_name='amountPaid', serialize_when_none=False, type=ModelType(Value))
    def contract_amountPaid(self):
        if self.amountPaid:
            return Value(dict(amount=self.amountPaid.amount,
                              currency=self.value.currency,
                              valueAddedTaxIncluded=self.value.valueAddedTaxIncluded))
