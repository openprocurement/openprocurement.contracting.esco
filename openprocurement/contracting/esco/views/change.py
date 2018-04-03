# -*- coding: utf-8 -*-
from openprocurement.contracting.api.utils import contractingresource
from openprocurement.contracting.common.views.change import (
    ContractsChangesResource as BaseContractsChangesResource
)


@contractingresource(
    name='Contract changes',
    collection_path='/contracts/{contract_id}/changes',
    path='/contracts/{contract_id}/changes/{change_id}',
    contractType='esco',
    description="Contracts Changes"
)
class ContractsChangesResource(BaseContractsChangesResource):
    """ ESCO Contract changes resource """
