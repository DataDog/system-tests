from utils import scenarios

from utils.scripts.ci_orchestrators.workflow_data import get_endtoend_definitions


@scenarios.test_the_test
def test_get_endtoend_definitions():
    scenario_map = {
        "endtoend": [
            "DEFAULT",
            "GRAPHQL_APPSEC",
        ],
    }

    defs = get_endtoend_definitions("ruby", scenario_map, [], "dev", 200000, 256)
    weblog_count = len(defs["endtoend_defs"]["parallel_weblogs"])

    # if there is an issue, ruby weblog count will be 0 or 1 or 2 ...
    assert weblog_count > 5

    # default scenario is executed on rails, sinatra and rack weblogs
    # graphql_appsec is executed on  graphql23 weblog
    # so the job should be equals to weblog count
    assert len(defs["endtoend_defs"]["parallel_jobs"]) == weblog_count
