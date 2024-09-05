import pytest
from utils import context


@pytest.fixture(
    params=getattr(context.scenario, "required_vms", []), ids=getattr(context.scenario, "required_vm_names", [])
)
def virtual_machine(request):
    yield request.param
