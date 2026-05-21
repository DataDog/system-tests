from utils import scenarios

from utils.scripts.ci_orchestrators.workflow_data import _is_supported, get_endtoend_definitions


@scenarios.test_the_test
def test_get_endtoend_definitions():
    scenario_map = {
        "endtoend": [
            "DEFAULT",
            "GRAPHQL_APPSEC",
        ],
    }

    defs = get_endtoend_definitions("ruby", scenario_map, [], "dev", 200000, 256, "123", "")
    weblog_count = len(defs["endtoend_defs"]["parallel_weblogs"])

    # if there is an issue, ruby weblog count will be 0 or 1 or 2 ...
    assert weblog_count > 5

    # default scenario is executed on rails, sinatra and rack weblogs
    # graphql_appsec is executed on  graphql23 weblog
    # so the job should be equals to weblog count
    assert len(defs["endtoend_defs"]["parallel_jobs"]) == weblog_count


@scenarios.test_the_test
def test_ipv6_is_not_supported_for_uds_weblogs():
    assert not _is_supported("dotnet", "uds", "IPV6", "dev")
    assert not _is_supported("python", "uds-flask", "IPV6", "dev")
    assert _is_supported("python", "flask-poc", "IPV6", "dev")
