import pytest
from typing import List, Tuple
import requests

from utils import context
from utils.tools import logger
from tests.onboarding.utils.provision_parser import Provision_parser, Provision_filter
import os
from tests.onboarding.utils.provision_matrix import ProvisionMatrix

provision_filter = Provision_filter(context.scenario.name)
provision_vms = ProvisionMatrix(provision_filter).get_infraestructure_provision()

logger.info(f"TENGO:::FIN")


@pytest.fixture(params=provision_vms)
def client(request):

    # the context scenario contains the provision vm detail with the current vm ip
    for provision_vm in context.scenario.provision_vms:
        if request.param.name == provision_vm.name:
            yield provision_vm
