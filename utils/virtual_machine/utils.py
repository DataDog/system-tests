import pytest
from utils import context
from utils._decorators import is_jira_ticket


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
    - Marks as bug for all vms that belong to "debian" and all weblogs
    *     @parametrize_virtual_machines(bugs=[{"vm_branch":"debian","reason": "APMON-1576"}])
    Reason is mandatory for each bug and it MUST reference to a JIRA ticket.
    """
    if callable(bugs):
        # here, bugs is not the bug list, but the decorated method
        raise TypeError(f"Typo in {bugs}'s decorator, you forgot parenthesis. Please use `@decorator()`")

    def decorator(func):
        # We group the parameters/vms. We want to execute in same worker the tests for one machine. We need to control the test order for each machine.
        # https://github.com/pytest-dev/pytest-xdist/issues/58
        parameters = []
        count = 0
        for vm in getattr(context.scenario, "required_vms", []):
            bug_found = False
            if bugs:
                for bug in bugs:
                    if (
                        (not "vm_name" in bug or vm.name == bug["vm_name"])
                        and (not "vm_branch" in bug or vm.os_branch == bug["vm_branch"])
                        and (not "vm_cpu" in bug or vm.os_cpu == bug["vm_cpu"])
                        and (not "weblog_variant" in bug or context.weblog_variant == bug["weblog_variant"])
                        and (not "library" in bug or context.library == bug["library"])
                    ):
                        if "reason" in bug and is_jira_ticket(bug["reason"]):
                            parameters.append(
                                pytest.param(
                                    vm,
                                    marks=[
                                        pytest.mark.xfail(reason=f"bug: {bug['reason']}"),
                                        pytest.mark.xdist_group(f"group{count}"),
                                    ],
                                )
                            )
                            bug_found = True
                            break
                        else:
                            raise ValueError(f"Invalid bug reason for {vm.name} {bug}. Please use a valid JIRA ticket.")

            if bug_found == False:
                parameters.append(pytest.param(vm, marks=pytest.mark.xdist_group(f"group{count}")))
            count += 1

        return pytest.mark.parametrize(
            "virtual_machine", parameters, ids=getattr(context.scenario, "required_vm_names", [])
        )(func)

    return decorator
