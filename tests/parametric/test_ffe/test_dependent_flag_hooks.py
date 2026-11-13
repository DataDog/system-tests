"""An OpenFeature after-hook failure must not expose any node of its dependency graph."""

import time
from collections import Counter
from typing import Any

from tests.ffe.utils.fixtures import make_ufc_fixture
from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.utils import ffe_events_from_requests
from utils import features, pytest, scenarios, slow
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI

ROOT = "after-hook-root"
PARENT = "after-hook-parent"
MARKERS = ("after-hook-rejected", "after-hook-retried", "after-hook-cached")
SUBJECT = "after-hook-subject"


def evaluate(test_library: APMLibrary, flag: str, *, fail_after: bool = False) -> dict[str, Any]:
    return test_library.ffe_evaluate(
        flag=flag,
        variation_type="STRING",
        default_value="fallback",
        targeting_key=SUBJECT,
        exposure_hooks=True,
        fail_after_hook=fail_after,
    )


def wait_for_marker(test_agent: TestAgentAPI, marker: str) -> None:
    # Both writers must pass a post-evaluation marker before asserting absence or counts.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        events = ffe_events_from_requests(test_agent.requests(), marker)
        if events["EXPOSURE"] and events["EVALUATION"]:
            return
        time.sleep(0.1)
    pytest.fail(f"Missing exposure/evaluation delivery marker {marker}: {events}")


def graph_exposures(test_agent: TestAgentAPI) -> list[dict[str, Any]]:
    requests = test_agent.requests()
    return [event for flag in (PARENT, ROOT) for event in ffe_events_from_requests(requests, flag)["EXPOSURE"]]


@scenarios.parametric
@features.feature_flags_exposures
@slow
class Test_FFE_Dependent_Flag_Hooks:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
                "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
                "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
                "DD_FLAGGING_EVALUATION_COUNTS_ENABLED": "true",
                "DD_FEATURE_FLAGS_EXPOSURES_DATADOG_LOGGING_ENABLED": "true",
                "SYSTEM_TESTS_FFE_OPENFEATURE": "true",
            }
        ],
    )
    @pytest.mark.parametrize("agent_env", [{"SYSTEM_TESTS_FFE_INTAKE": "true"}])
    def test_after_hook_failure_preserves_graph_exposures(
        self, test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        fixture = make_ufc_fixture(ROOT)
        for flag in (PARENT, *MARKERS):
            fixture["flags"].update(make_ufc_fixture(flag)["flags"])
        fixture["flags"][ROOT]["allocations"][0]["rules"] = [
            {
                "conditions": [
                    {
                        "flagEvaluation": {"key": PARENT},
                        "operator": "ONE_OF",
                        "value": ["on"],
                    }
                ]
            }
        ]
        test_agent.set_remote_config(path="datadog/2/FFE_FLAGS/after-hooks/config", payload=fixture)
        # Startup may time out before the first RC poll; it still registers the provider.
        test_library.ffe_start()
        test_agent.wait_for_rc_apply_state(
            "FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id="after-hooks", wait_loops=500
        )
        assert test_library.ffe_start()

        rejected = evaluate(test_library, ROOT, fail_after=True)
        assert rejected["value"] == "fallback", rejected
        assert rejected["reason"] == "ERROR", rejected
        assert rejected["errorCode"] == "GENERAL", rejected
        assert evaluate(test_library, MARKERS[0])["value"] == "on-value"
        wait_for_marker(test_agent, MARKERS[0])
        assert graph_exposures(test_agent) == []
        for flag in (PARENT, ROOT):
            records = ffe_events_from_requests(test_agent.requests(), flag)["EVALUATION"]
            assert sum(record["evaluation_count"] for record in records) == 1, records

        expected = Counter((flag, "default-allocation", "on", SUBJECT) for flag in (PARENT, ROOT))
        for marker in MARKERS[1:]:
            accepted = evaluate(test_library, ROOT)
            assert accepted["value"] == "on-value", accepted
            assert accepted["reason"] == "TARGETING_MATCH", accepted
            assert accepted["errorCode"] in (None, ""), accepted
            assert evaluate(test_library, marker)["value"] == "on-value"
            wait_for_marker(test_agent, marker)
            exposures = graph_exposures(test_agent)
            assert (
                Counter(
                    (event["flag"]["key"], event["allocation"]["key"], event["variant"]["key"], event["subject"]["id"])
                    for event in exposures
                )
                == expected
            ), exposures
