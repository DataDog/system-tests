import pytest
import requests
from utils import context


@pytest.fixture(
    params=getattr(context.scenario, "provision_vms", []), ids=getattr(context.scenario, "provision_vm_names", [])
)
def onboardig_vm(request):

    yield request.param
