"""Dependent-flag capability and evaluation contract on the Agent RC transport.

Supported and legacy builds have separate manifest-controlled expectations. Never
infer support from the advertised bit: doing so would hide a missing-bit regression.
"""

import time
from typing import Any

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_ffe.utils import assert_dependent_flag_capability
from utils import features, pytest, scenarios
from utils.dd_constants import RemoteConfigApplyState
from utils.docker_fixtures import TestAgentAPI

RC_PRODUCT = "FFE_FLAGS"
ENV = {
    "DD_EXPERIMENTAL_FLAGGING_PROVIDER_ENABLED": "true",
    "DD_FEATURE_FLAGS_ENABLED": "true",
    "DD_FEATURE_FLAGS_CONFIGURATION_SOURCE": "remote_config",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
}


def _ffe_requests(test_agent: TestAgentAPI) -> list[dict[str, Any]]:
    return [
        request
        for request in test_agent.rc_requests(post_only=True)
        if RC_PRODUCT in request["body"]["client"].get("products", [])
    ]


def _observe_polls(test_agent: TestAgentAPI, *, supported: bool, minimum: int = 3) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        requests = _ffe_requests(test_agent)
        if requests:
            assert_dependent_flag_capability(requests, supported=supported)
        if len(requests) >= minimum:
            return
        time.sleep(0.1)
    raise AssertionError(f"Expected at least {minimum} FFE_FLAGS RC polls, got {len(requests)}")


def _config(*, parent_variant: str, dependent: bool) -> dict[str, Any]:
    parent = {
        "key": "parent",
        "enabled": True,
        "variationType": "STRING",
        # The selected variant key deliberately differs from its value.
        "variations": {
            "approved": {"key": "approved", "value": "not-the-variant-key"},
            "rejected": {"key": "rejected", "value": "approved"},
        },
        "allocations": [
            {"key": "parent-default", "splits": [{"variationKey": parent_variant, "shards": []}], "doLog": False}
        ],
    }
    flags = {"parent": parent}
    if dependent:
        flags["child"] = {
            "key": "child",
            "enabled": True,
            "variationType": "STRING",
            "variations": {key: {"key": key, "value": key} for key in ("matched", "unmatched")},
            "allocations": [
                {
                    "key": "prerequisite",
                    "rules": [
                        {
                            "conditions": [
                                {"flagEvaluation": {"key": "parent"}, "operator": "ONE_OF", "value": ["approved"]}
                            ]
                        }
                    ],
                    "splits": [{"variationKey": "matched", "shards": []}],
                    "doLog": False,
                },
                {"key": "fallback", "splits": [{"variationKey": "unmatched", "shards": []}], "doLog": False},
            ],
        }
    return {"createdAt": "2026-11-03T00:00:00Z", "format": "SERVER", "environment": {"name": "test"}, "flags": flags}


def _deliver(test_agent: TestAgentAPI, *, config_id: str, parent_variant: str, dependent: bool) -> None:
    test_agent.set_remote_config(
        path=f"datadog/2/{RC_PRODUCT}/{config_id}/config",
        payload=_config(parent_variant=parent_variant, dependent=dependent),
    )
    test_agent.wait_for_rc_apply_state(
        RC_PRODUCT,
        state=RemoteConfigApplyState.ACKNOWLEDGED,
        config_id=config_id,
        wait_loops=1000,
    )


def _assert_value(test_library: APMLibrary, flag: str, value: str) -> None:
    deadline = time.monotonic() + 5
    while True:
        result = test_library.ffe_evaluate(
            flag=flag,
            variation_type="STRING",
            default_value="caller-default",
            targeting_key="subject",
        )
        if result.get("value") == value and result.get("errorCode") in (None, ""):
            return
        assert time.monotonic() < deadline, result
        time.sleep(0.1)


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_FFE_Dependent_Flags_RC:
    @pytest.mark.parametrize("library_env", [ENV])
    def test_capability_and_gated_delivery(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Advertise before delivery, evaluate variant keys, and retain the bit after updates."""
        assert test_library.ffe_start(), "Failed to initialize the provider"
        # No inline configuration: only RC can deliver these flag definitions.
        _observe_polls(test_agent, supported=True)
        for variant, expected in (("approved", "matched"), ("rejected", "unmatched")):
            assert_dependent_flag_capability(_ffe_requests(test_agent), supported=True)
            _deliver(test_agent, config_id="dependent-flags", parent_variant=variant, dependent=True)
            _assert_value(test_library, "child", expected)
            previous_count = len(_ffe_requests(test_agent))
            _observe_polls(test_agent, supported=True, minimum=previous_count + 2)


@scenarios.parametric
@features.feature_flags_dynamic_evaluation
class Test_FFE_Without_Dependent_Flags_RC:
    @pytest.mark.parametrize("library_env", [ENV])
    def test_legacy_build_does_not_advertise(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """A known legacy build receives ordinary flags and never advertises bit 50."""
        assert test_library.ffe_start(), "Failed to initialize the provider"
        _observe_polls(test_agent, supported=False)
        _deliver(test_agent, config_id="ordinary-flags", parent_variant="approved", dependent=False)
        _assert_value(test_library, "parent", "not-the-variant-key")
        previous_count = len(_ffe_requests(test_agent))
        _observe_polls(test_agent, supported=False, minimum=previous_count + 2)
