import pytest
from typing import List, Tuple
import requests

from utils import context
from utils.tools import logger
import os


@pytest.fixture(params=context.scenario.provision_vms)
def onboardig_vm_ip(request):

    yield request.param.ip
