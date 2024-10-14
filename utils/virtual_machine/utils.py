import pytest
from utils import context


def parametrize_virtual_machines(bugs: list[dict] = None):
    """ You can set multiple bugs for a single test case. 
    If you want to set a bug for a specific VM, you can set the vm_name or vm_cpu or weblog_variant in the bug dictionary (using one or more fields). 
    ie: 
    - Marks as bug for vm with name "vm1" and weblog_variant "app1"
    *     @parametrize_virtual_machines(bugs=[{"vm_name":"vm1", "weblog_variant":"app1", "reason": "APMON-1576"}])
    - Marks as bug for vm with cpu type "amd64" and weblog_variant "app1"
    *     @parametrize_virtual_machines(bugs=[{"vm_cpu":"amd64", "weblog_variant":"app1", "reason": "APMON-1576"}])
    - Marks as bug for all vm with cpu type "amd64" and all weblogs
    *     @parametrize_virtual_machines(bugs=[{"vm_cpu":"amd64","reason": "APMON-1576"}])
    Reason is mandatory for each bug and it MUST reference to a JIRA ticket.
    """

    def decorator(func):

        parameters = []

        for vm in getattr(context.scenario, "required_vms", []):
            bug_found = False
            if bugs and hasattr(bugs, "__len__") and len(bugs) > 0:
                for bug in bugs:
                    if (
                        ("vm_name" not in bug or vm.name == bug["vm_name"])
                        and (not "vm_cpu" in bug or vm.os_cpu == bug["vm_cpu"])
                        and (not "weblog_variant" in bug or context.weblog_variant == bug["weblog_variant"])
                    ):
                        parameters.append(pytest.param(vm, marks=pytest.mark.xfail(reason=f"bug: {bug['reason']}")))
                        bug_found = True
                        break

            if bug_found == False:
                parameters.append(vm)

        return pytest.mark.parametrize("virtual_machine", parameters)(func)

    return decorator
