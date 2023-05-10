import pytest
from typing import List, Tuple
import requests

from utils import context
from utils.tools import logger
import os


@pytest.fixture(params=context.scenario.provision_vms, ids=context.scenario.provision_vm_names)
def onboardig_vm(request):

    yield request.param
