import pytest
import requests
from utils import context
from utils.tools import logger


@pytest.fixture(
    params=getattr(context.scenario, "provision_vms", []),
    ids=getattr(context.scenario, "provision_vm_names", []),
)
def onboardig_vm(request):
    pytestmark = request.param.pytestmark
    if pytestmark is not None:
        request.node.add_marker(pytest.mark.xfail(reason=pytestmark))
    yield request.param
