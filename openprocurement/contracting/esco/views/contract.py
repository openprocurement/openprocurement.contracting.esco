# -*- coding: utf-8 -*-
from openprocurement.contracting.api.utils import contractingresource
from openprocurement.contracting.common.views.contract import (
    ContractResource as BaseContractResource,
)


@contractingresource(name='esco:Contract',
                     path='/contracts/{contract_id}',
                     contractType='esco',
                     description="Contract")
class ContractResource(BaseContractResource):
    """ ESCO Contract Resource """
