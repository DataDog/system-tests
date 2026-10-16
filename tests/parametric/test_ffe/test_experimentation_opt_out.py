"""Exercise shared experimentation opt-out inputs through a real Java provider.

This suite checks assignment behavior, not per-case exposure counts. Exposure
deduplication is process-wide. The isolated dogfooding suite checks emissions.
Time-gated generated cases stay in fixed-clock SDK tests and guarded dogfooding.
The shared configurations and expected results are never rewritten for runtime.
"""

import hashlib
import json
import time
from collections import defaultdict
from typing import Any

from utils import features, pytest, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import ParametricTestClientApi as APMLibrary, TestAgentAPI
from tests.parametric.test_ffe.experimentation_contract import assert_details, has_time_boundary, load_contract

MANIFEST, CONFIGURATIONS, CASES = load_contract()
GROUPS: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
for case in CASES:
    if not has_time_boundary(CONFIGURATIONS[case["configuration"]], case):
        GROUPS[(case["configuration"], json.dumps(case["providerOptions"], sort_keys=True))].append(case)

DEFAULT_ENVVARS = {
    "DD_FEATURE_FLAGS_ENABLED": "true",
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
    # Ordinary allocations expose serial metadata when this existing feature is enabled.
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_SPAN_ENRICHMENT_ENABLED": "true",
}


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_Feature_Flag_Experimentation_Opt_Out:
    """Compare exact shared assignments with explicitly activated public options."""

    @pytest.mark.parametrize("library_env", [DEFAULT_ENVVARS])
    @pytest.mark.parametrize("group", list(GROUPS), ids=[f"{key[0]}-{index}" for index, key in enumerate(GROUPS)])
    def test_shared_contract(self, group: tuple[str, str], test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        configuration_id, options_json = group
        configuration = CONFIGURATIONS[configuration_id]
        config_id = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
        test_agent.set_remote_config(path=f"datadog/2/FFE_FLAGS/{config_id}/config", payload=configuration)
        state = test_agent.wait_for_rc_apply_state(
            "FFE_FLAGS", state=RemoteConfigApplyState.ACKNOWLEDGED, config_id=config_id, wait_loops=500, clear=True
        )
        assert state["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED.value
        assert test_library.ffe_start(configuration, provider_options=json.loads(options_json))
        for case in GROUPS[group]:
            evaluation = case["evaluation"]
            for attempt in range(10):
                result = test_library.ffe_evaluate(
                    flag=evaluation["flag"],
                    variation_type=evaluation["variationType"],
                    default_value=evaluation["defaultValue"],
                    targeting_key=case["context"]["targetingKey"],
                    attributes=case["context"].get("attributes", {}),
                )
                if result.get("errorCode") != "PROVIDER_NOT_READY" or attempt == 9:
                    break
                time.sleep(0.2)
            assert_details(result, case)
