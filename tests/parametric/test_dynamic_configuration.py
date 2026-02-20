"""Test the dynamic configuration via Remote Config (RC) feature of the APM libraries."""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from utils import (
    context,
    features,
    irrelevant,
    missing_feature,
    rfc,
    scenarios,
)
from utils._context.component_version import ComponentVersion
from utils.docker_fixtures import TestAgentAPI
from utils.dd_constants import Capabilities, RemoteConfigApplyState
from utils.docker_fixtures.spec.trace import (
    Span,
    assert_trace_has_tags,
    find_trace,
    find_first_span_in_trace_payload,
)
from utils.manifest._internal.types import SemverRange
from .conftest import APMLibrary

parametrize = pytest.mark.parametrize


DEFAULT_SAMPLE_RATE = 1.0
TEST_SERVICE = "test_service"
TEST_ENV = "test_env"
DEFAULT_ENVVARS = {
    "DD_SERVICE": TEST_SERVICE,
    "DD_ENV": TEST_ENV,
    # Needed for .NET until Telemetry V2 is released
    "DD_INTERNAL_TELEMETRY_V2_ENABLED": "1",
    # Decrease the heartbeat/poll intervals to speed up the tests
    "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.2",
    "DD_REMOTE_CONFIG_POLL_INTERVAL_SECONDS": "0.2",
    # Disable CSS which is enabled by default on Go
    "DD_TRACE_STATS_COMPUTATION_ENABLED": "false",
}


def send_and_wait_trace(
    test_library: APMLibrary,
    test_agent: TestAgentAPI,
    name: str,
    service: str | None = None,
    resource: str | None = None,
    parent_id: str | int | None = None,
    typestr: str | None = None,
    tags: list[tuple[str, str]] | None = None,
) -> list[Span]:
    with test_library.dd_start_span(
        name=name,
        service=service,
        resource=resource,
        parent_id=parent_id,
        typestr=typestr,
        tags=tags,
    ) as s1:
        pass
    test_library.dd_flush()
    traces = test_agent.wait_for_num_traces(num=1, clear=True, sort_by_start=False)
    return find_trace(traces, s1.trace_id)


def _load_capabilities_yaml() -> dict[str, Any]:
    """Load and parse the capabilities.yml file."""
    capabilities_file = Path(__file__).parent / "capabilities.yml"

    if not capabilities_file.exists():
        raise FileNotFoundError(
            f"Capabilities file not found: {capabilities_file}. "
            "This file defines expected Remote Config capabilities per language and version."
        )

    with open(capabilities_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "capabilities" not in data:
        raise ValueError("Invalid capabilities.yml: missing 'capabilities' section")

    return data


def get_expected_capabilities_for_version(library: ComponentVersion) -> set[Capabilities]:
    """Get the expected set of Remote Config capabilities for a given library version."""
    data = _load_capabilities_yaml()

    language = library.name
    if language not in data["capabilities"]:
        raise ValueError(
            f"Language '{language}' not found in capabilities.yml. "
            f"Available languages: {list(data['capabilities'].keys())}"
        )

    lang_config = data["capabilities"][language]

    # Start with base capabilities (always present)
    if "base" not in lang_config:
        raise ValueError(f"Missing 'base' capability set for language '{language}' in capabilities.yml")

    capabilities: set[Capabilities] = set()

    # Add base capabilities
    for cap_name in lang_config["base"]:
        try:
            capabilities.add(Capabilities[cap_name])
        except KeyError as e:
            raise KeyError(
                f"Unknown capability '{cap_name}' in capabilities.yml for language '{language}'. "
                f"Check utils/dd_constants.py for valid Capabilities enum values."
            ) from e

    # Add version-specific capabilities
    for key, cap_list in lang_config.items():
        if key == "base":
            continue  # Already processed

        # Parse the version range
        try:
            version_range = SemverRange(key)
        except Exception as e:
            raise ValueError(f"Invalid version range '{key}' in capabilities.yml for language '{language}': {e}") from e

        # Check if the library version matches this range
        if library.version and library.version in version_range:
            for cap_name in cap_list:
                try:
                    capabilities.add(Capabilities[cap_name])
                except KeyError as e:
                    raise KeyError(
                        f"Unknown capability '{cap_name}' in capabilities.yml for "
                        f"language '{language}' version range '{key}'. "
                        f"Check utils/dd_constants.py for valid Capabilities enum values."
                    ) from e

    return capabilities


def _default_config(service: str, env: str) -> dict[str, Any]:
    return {
        "action": "enable",
        "revision": 1698167126064,
        "service_target": {"service": service, "env": env},
        "lib_config": {
            # v1 dynamic config
            "tracing_sampling_rate": None,
            "log_injection_enabled": None,
            "tracing_header_tags": None,
            # v2 dynamic config
            "runtime_metrics_enabled": None,
            "tracing_debug": None,
            "tracing_service_mapping": None,
            "tracing_sampling_rules": None,
            "data_streams_enabled": None,
            "dynamic_instrumentation_enabled": None,
            "exception_replay_enabled": None,
            "code_origin_enabled": None,
            "live_debugging_enabled": None,
        },
    }


def _set_rc(test_agent: TestAgentAPI, config: dict[str, Any], config_id: str | None = None) -> None:
    if not config_id:
        config_id = str(hash(json.dumps(config)))

    config["id"] = str(config_id)
    test_agent.set_remote_config(path=f"datadog/2/APM_TRACING/{config_id}/config", payload=config)


def _create_rc_config(config_overrides: dict[str, Any]) -> dict:
    rc_config = _default_config(TEST_SERVICE, TEST_ENV)
    for k, v in config_overrides.items():
        rc_config["lib_config"][k] = v
    return rc_config


def set_and_wait_rc(test_agent: TestAgentAPI, config_overrides: dict[str, Any], config_id: str | None = None) -> dict:
    """Helper to create an RC configuration with the given settings and wait for it to be applied.

    It is assumed that the configuration is successfully applied.
    """
    rc_config = _create_rc_config(config_overrides)

    _set_rc(test_agent, rc_config, config_id)

    # Wait for both the telemetry event and the RC apply status.
    test_agent.wait_for_telemetry_event("app-client-configuration-change", clear=True)
    return test_agent.wait_for_rc_apply_state("APM_TRACING", state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)


def assert_sampling_rate(trace: list[dict], rate: float):
    """Asserts that a trace returned from the test agent is consistent with the given sample rate.

    This function assumes that all traces are sent to the agent regardless of sample rate.

    For the day when that is not the case, we likely need to generate enough traces to
        1) Validate the sample rate is effective (approx sample_rate% of traces should be received)
        2) The `_dd.rule_psr` metric is set to the correct value.
    """
    # This tag should be set on the first span in a chunk (first span in the list of spans sent to the agent).
    span = find_first_span_in_trace_payload(trace)
    assert span["metrics"].get("_dd.rule_psr", 1.0) == pytest.approx(rate)


def is_sampled(trace: list[dict]):
    """Asserts that a trace returned from the test agent is consistent with the given sample rate.

    This function assumes that all traces are sent to the agent regardless of sample rate.

    For the day when that is not the case, we likely need to generate enough traces to
        1) Validate the sample rate is effective (approx sample_rate% of traces should be received)
        2) The `_dd.rule_psr` metric is set to the correct value.
    """

    # This tag should be set on the first span in a chunk (first span in the list of spans sent to the agent).
    span = find_first_span_in_trace_payload(trace)
    return span["metrics"].get("_sampling_priority_v1", 0) > 0


def get_sampled_trace(
    test_library: APMLibrary,
    test_agent: TestAgentAPI,
    service: str,
    name: str,
    tags: list[tuple[str, str]] | None = None,
) -> list[Span]:
    trace = None
    while not trace or not is_sampled(trace):
        trace = send_and_wait_trace(test_library, test_agent, service=service, name=name, tags=tags)
    return trace


ENV_SAMPLING_RULE_RATE = 0.55


@scenarios.parametric
@features.dynamic_configuration
class TestDynamicConfigTracingEnabled:
    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_default_capability_completeness(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the RC request contains the expected default capabilities per language.

        For released versions: expects exact match (no more, no less).
        For pre-release versions: allows extra capabilities to support chicken-and-egg development.
        """

        assert test_library.is_alive(), "library container is not alive"

        if context.library is not None and context.library.name is not None:
            seen_capabilities = test_agent.wait_for_rc_capabilities()
            expected_capabilities = get_expected_capabilities_for_version(context.library)

            expected_but_not_seen_capabilities = expected_capabilities.difference(seen_capabilities)

            # Always fail if expected capabilities are missing
            if expected_but_not_seen_capabilities:
                raise AssertionError(
                    f"expected_but_not_seen_capabilities={expected_but_not_seen_capabilities}; "
                    f"Update capabilities.yml to fix this."
                )

            # For released versions, enforce strict equality (no extra capabilities)
            # For pre-release versions, allow extra capabilities (solves chicken-and-egg problem)
            is_prerelease = context.library.version and context.library.version.prerelease

            if not is_prerelease:
                seen_but_not_expected_capabilities = seen_capabilities.difference(expected_capabilities)
                if seen_but_not_expected_capabilities:
                    raise AssertionError(
                        f"seen_but_not_expected_capabilities={seen_but_not_expected_capabilities}; "
                        f"Update capabilities.yml to fix this."
                    )

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_enabled(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the RC request contains the tracing enabled capability."""
        assert test_library.is_alive(), "library container is not alive"
        test_agent.assert_rc_capabilities({Capabilities.APM_TRACING_ENABLED})

    @parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS}, {**DEFAULT_ENVVARS, "DD_TRACE_ENABLED": "false"}],
    )
    def test_tracing_client_tracing_enabled(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        trace_enabled_env = library_env.get("DD_TRACE_ENABLED", "true") == "true"
        if trace_enabled_env:
            with test_library, test_library.dd_start_span("allowed"):
                pass
            test_agent.wait_for_num_traces(num=1, clear=True)
            assert True, (
                "DD_TRACE_ENABLED=true and unset results in a trace being sent."
                "wait_for_num_traces does not raise an exception."
            )

        _set_rc(test_agent, _create_rc_config({"tracing_enabled": False}))
        # if tracing is disabled via DD_TRACE_ENABLED, the RC should not re-enable it
        # nor should it send RemoteConfig apply state
        if trace_enabled_env:
            test_agent.wait_for_telemetry_event("app-client-configuration-change", clear=True)
            test_agent.wait_for_rc_apply_state("APM_TRACING", state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)
        with test_library, test_library.dd_start_span("disabled"):
            pass
        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1, clear=True)
        assert True, "no traces are sent after RC response with tracing_enabled: false"

    @parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS}, {**DEFAULT_ENVVARS, "DD_TRACE_ENABLED": "false"}],
    )
    def test_tracing_client_tracing_disable_one_way(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        trace_enabled_env = library_env.get("DD_TRACE_ENABLED", "true") == "true"

        _set_rc(test_agent, _create_rc_config({"tracing_enabled": False}))
        if trace_enabled_env:
            test_agent.wait_for_telemetry_event("app-client-configuration-change", clear=True)
            test_agent.wait_for_rc_apply_state("APM_TRACING", state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)

        _set_rc(test_agent, _create_rc_config({}))
        test_agent.wait_for_rc_apply_state("APM_TRACING", state=RemoteConfigApplyState.ACKNOWLEDGED, clear=True)
        with test_library, test_library.dd_start_span("test"):
            pass

        with pytest.raises(ValueError):
            test_agent.wait_for_num_traces(num=1, clear=True)
        assert True, (
            "no traces are sent after tracing_enabled: false, even after an RC response with a different setting"
        )


def reverse_case(s: str) -> str:
    return "".join([char.lower() if char.isupper() else char.upper() for char in s])


@rfc("https://docs.google.com/document/d/1SVD0zbbAAXIsobbvvfAEXipEUO99R9RMsosftfe9jx0")
@scenarios.parametric
@features.dynamic_configuration
@features.adaptive_sampling
class TestDynamicConfigV1:
    """Tests covering the v1 release of the dynamic configuration feature.

    v1 includes support for:
        - tracing_sampling_rate
        - log_injection_enabled
    """

    @parametrize("library_env", [{"DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.1"}])
    def test_telemetry_app_started(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that the app-started telemetry event is being submitted.

        Telemetry events are used as a signal for the configuration being applied
        by the library.
        """
        # Python doesn't start writing telemetry until the first trace.
        with test_library.dd_start_span("test"):
            pass
        events = test_agent.wait_for_telemetry_event("app-started")
        assert len(events) > 0

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_apply_state(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Create a default RC record and ensure the apply_state is correctly set.

        This signal, along with the telemetry event, is used to determine when the
        configuration has been applied by the tracer.
        """
        assert test_library.is_alive(), "library container is not alive"
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": 0.5})
        cfg_state = test_agent.wait_for_rc_apply_state("APM_TRACING", state=RemoteConfigApplyState.ACKNOWLEDGED)
        assert cfg_state["apply_state"] == 2
        assert cfg_state["product"] == "APM_TRACING"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_trace_sampling_rate_override_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """The RC sampling rate should override the default sampling rate.

        When RC is unset, the default should be used again.
        """
        # Create an initial trace to assert the default sampling settings.
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

        # Create a remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": 0.5})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, 0.5)

        # Unset the RC sample rate to ensure the default setting is used.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": None})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

    @parametrize(
        "library_env",
        [{"DD_TRACE_SAMPLE_RATE": r, **DEFAULT_ENVVARS} for r in ["0.1", "1.0"]],
    )
    def test_trace_sampling_rate_override_env(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """The RC sampling rate should override the environment variable.

        When RC is unset, the environment variable should be used.
        """
        trace_sample_rate_env = library_env["DD_TRACE_SAMPLE_RATE"]
        if trace_sample_rate_env is None:
            initial_sample_rate = DEFAULT_SAMPLE_RATE
        else:
            initial_sample_rate = float(trace_sample_rate_env)

        # Create an initial trace to assert the default sampling settings.
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, initial_sample_rate)

        # Create a remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        rc_state = set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": 0.5})
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, 0.5)

        # Keep a reference on the RC config id
        config_id = rc_state["id"]

        # Create another remote config entry, wait for the configuration change telemetry event to be received
        # and then create a new trace to assert the configuration has been applied.
        set_and_wait_rc(
            test_agent,
            config_overrides={"tracing_sampling_rate": 0.6},
            config_id=config_id,
        )
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, 0.6)

        # Unset the RC sample rate to ensure the previous setting is reapplied.
        set_and_wait_rc(
            test_agent,
            config_overrides={"tracing_sampling_rate": None},
            config_id=config_id,
        )
        trace = send_and_wait_trace(test_library, test_agent, name="test")
        assert_sampling_rate(trace, initial_sample_rate)

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": ENV_SAMPLING_RULE_RATE, "name": "env_name"}]),
            }
        ],
    )
    def test_trace_sampling_rate_with_sampling_rules(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that sampling rules still apply when the sample rate is set via remote config."""
        rc_sampling_rule_rate = 0.70
        assert rc_sampling_rule_rate != ENV_SAMPLING_RULE_RATE

        # Create an initial trace to assert that the rule is correctly applied.
        trace = send_and_wait_trace(test_library, test_agent, name="env_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)

        # Create a remote config entry with a different sample rate. This rate should not
        # apply to env_service spans but should apply to all others.
        set_and_wait_rc(
            test_agent,
            config_overrides={"tracing_sampling_rate": rc_sampling_rule_rate},
        )

        trace = send_and_wait_trace(test_library, test_agent, name="env_name", service="")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        trace = send_and_wait_trace(test_library, test_agent, name="other_name")
        assert_sampling_rate(trace, rc_sampling_rule_rate)

        # Unset the RC sample rate to ensure the previous setting is reapplied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": None})
        trace = send_and_wait_trace(test_library, test_agent, name="env_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        trace = send_and_wait_trace(test_library, test_agent, name="other_name")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

    @missing_feature(
        context.library in ("cpp", "golang"),
        reason="Tracer doesn't support automatic logs injection",
    )
    @parametrize(
        "library_env",
        [
            {"DD_TRACE_LOGS_INJECTION": "true", **DEFAULT_ENVVARS},
            {"DD_TRACE_LOGS_INJECTION": "false", **DEFAULT_ENVVARS},
            {**DEFAULT_ENVVARS},
        ],
    )
    def test_log_injection_enabled(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure that the log injection setting can be set.

        There is no way (at the time of writing) to check the logs produced by the library.
        """
        assert test_library.is_alive(), "library container is not alive"
        cfg_state = set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rate": None})
        assert cfg_state["apply_state"] == 2


@rfc("https://docs.google.com/document/d/1SVD0zbbAAXIsobbvvfAEXipEUO99R9RMsosftfe9jx0")
@scenarios.parametric
@features.dynamic_configuration
@features.adaptive_sampling
class TestDynamicConfigV1_EmptyServiceTargets:
    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                # Override service and env
                "DD_SERVICE": s,
                "DD_ENV": e,
            }
            for (s, e) in [
                # empty service
                ("", DEFAULT_ENVVARS["DD_ENV"]),
                # empty env
                (DEFAULT_ENVVARS["DD_SERVICE"], ""),
                # empty service and empty env
                ("", ""),
            ]
        ],
    )
    def test_not_match_service_target_empty_env(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that the library reports a non-erroneous apply_state when DD_SERVICE or DD_ENV are empty."""
        assert test_library.is_alive(), "library container is not alive"
        _set_rc(test_agent, _default_config(TEST_SERVICE, TEST_ENV))

        # C++ make RC requests every second -> update is a bit slower to propagate.
        wait_loops = 1000 if context.library == "cpp" else 100

        cfg_state = test_agent.wait_for_rc_apply_state(
            "APM_TRACING", state=RemoteConfigApplyState.ACKNOWLEDGED, wait_loops=wait_loops
        )
        assert cfg_state["apply_state"] == 2


@rfc("https://docs.google.com/document/d/1SVD0zbbAAXIsobbvvfAEXipEUO99R9RMsosftfe9jx0")
@scenarios.parametric
@features.dynamic_configuration
@features.adaptive_sampling
class TestDynamicConfigV1_ServiceTargets:
    """Tests covering the Service Target matching of the dynamic configuration feature.

    - ignore mismatching targets
    - matching service target case-insensitively
    """

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                # Override service and env
                "DD_SERVICE": s,
                "DD_ENV": e,
            }
            for (s, e) in [
                (
                    DEFAULT_ENVVARS["DD_SERVICE"] + "-override",
                    DEFAULT_ENVVARS["DD_ENV"],
                ),
                (
                    DEFAULT_ENVVARS["DD_SERVICE"],
                    DEFAULT_ENVVARS["DD_ENV"] + "-override",
                ),
                (
                    DEFAULT_ENVVARS["DD_SERVICE"] + "-override",
                    DEFAULT_ENVVARS["DD_ENV"] + "-override",
                ),
            ]
        ],
    )
    def test_not_match_service_target(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """This is an old behavior, see APMAPI-1003

        ----

        Test that the library reports an erroneous apply_state when the service targeting is not correct.

        This can occur if the library requests Remote Configuration with an initial service + env pair and then
        one or both of the values changes.

        We simulate this condition by setting DD_SERVICE and DD_ENV to values that differ from the service
        target in the RC record.
        """
        assert test_library.is_alive(), "library container is not alive"
        _set_rc(test_agent, _default_config(TEST_SERVICE, TEST_ENV))

        # C++ make RC requests every second -> update is a bit slower to propagate.
        wait_loops = 1000 if context.library == "cpp" else 100

        cfg_state = test_agent.wait_for_rc_apply_state(
            "APM_TRACING", state=RemoteConfigApplyState.ERROR, wait_loops=wait_loops
        )
        assert cfg_state["apply_state"] == RemoteConfigApplyState.ERROR.value
        assert cfg_state["apply_error"] != ""

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                # Override service and env
                "DD_SERVICE": s,
                "DD_ENV": e,
            }
            for (s, e) in [
                (
                    reverse_case(DEFAULT_ENVVARS["DD_SERVICE"]),
                    DEFAULT_ENVVARS["DD_ENV"],
                ),
                (
                    DEFAULT_ENVVARS["DD_SERVICE"],
                    reverse_case(DEFAULT_ENVVARS["DD_ENV"]),
                ),
                (
                    reverse_case(DEFAULT_ENVVARS["DD_SERVICE"]),
                    reverse_case(DEFAULT_ENVVARS["DD_ENV"]),
                ),
            ]
        ],
    )
    def test_match_service_target_case_insensitively(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Test that the library reports a non-erroneous apply_state when the service targeting is correct but differ in case.

        This can occur if the library requests Remote Configuration with an initial service + env pair and then
        one or both of the values changes its case.

        We simulate this condition by setting DD_SERVICE and DD_ENV to values that differ only in case from the service
        target in the RC record.
        """
        assert test_library.is_alive(), "library container is not alive"
        _set_rc(test_agent, _default_config(TEST_SERVICE, TEST_ENV))
        cfg_state = test_agent.wait_for_rc_apply_state("APM_TRACING", state=RemoteConfigApplyState.ACKNOWLEDGED)
        assert cfg_state["apply_state"] == 2


@rfc("https://docs.google.com/document/d/1V4ZBsTsRPv8pAVG5WCmONvl33Hy3gWdsulkYsE4UZgU/edit")
@scenarios.parametric
@features.dynamic_configuration
@features.adaptive_sampling
class TestDynamicConfigV2:
    @parametrize(
        "library_env",
        [{**DEFAULT_ENVVARS}, {**DEFAULT_ENVVARS, "DD_TAGS": "key1:val1,key2:val2"}],
    )
    def test_tracing_client_tracing_tags(
        self, library_env: dict[str, str], test_agent: TestAgentAPI, test_library: APMLibrary
    ) -> None:
        expected_local_tags: dict[str, int | str | float | bool] = {}
        if "DD_TAGS" in library_env:
            expected_local_tags: dict[str, int | str | float | bool] = dict(
                [p.split(":") for p in library_env["DD_TAGS"].split(",")]
            )

        # Ensure tags are applied from the env
        with (
            test_library,
            test_library.dd_start_span("test") as span,
            test_library.dd_start_span("test2", parent_id=span.span_id),
        ):
            pass
        traces = test_agent.wait_for_num_traces(num=1, clear=True, sort_by_start=False)
        assert_trace_has_tags(traces[0], expected_local_tags)

        # Ensure local tags are overridden and RC tags applied.
        set_and_wait_rc(
            test_agent,
            config_overrides={"tracing_tags": ["rc_key1:val1", "rc_key2:val2"]},
        )
        with (
            test_library,
            test_library.dd_start_span("test") as span,
            test_library.dd_start_span("test2", parent_id=span.span_id),
        ):
            pass
        traces = test_agent.wait_for_num_traces(num=1, clear=True, sort_by_start=False)
        assert_trace_has_tags(traces[0], {"rc_key1": "val1", "rc_key2": "val2"})

        # Ensure previous tags are restored.
        set_and_wait_rc(test_agent, config_overrides={})
        with (
            test_library,
            test_library.dd_start_span("test") as span,
            test_library.dd_start_span("test2", parent_id=span.span_id),
        ):
            pass
        traces = test_agent.wait_for_num_traces(num=1, clear=True, sort_by_start=False)
        assert_trace_has_tags(traces[0], expected_local_tags)

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_sampling_rate(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the RC request contains the trace sampling rate capability."""
        assert test_library.is_alive(), "library container is not alive"
        test_agent.assert_rc_capabilities({Capabilities.APM_TRACING_SAMPLE_RATE})

    @irrelevant(
        context.library in ("cpp", "golang"),
        reason="Tracer doesn't support automatic logs injection",
    )
    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_logs_injection(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the RC request contains the logs injection capability."""
        assert test_library.is_alive(), "library container is not alive"
        test_agent.assert_rc_capabilities({Capabilities.APM_TRACING_LOGS_INJECTION})

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_http_header_tags(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the RC request contains the http header tags capability."""
        assert test_library.is_alive(), "library container is not alive"
        test_agent.assert_rc_capabilities({Capabilities.APM_TRACING_HTTP_HEADER_TAGS})

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_custom_tags(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the RC request contains the custom tags capability."""
        assert test_library.is_alive(), "library container is not alive"
        test_agent.assert_rc_capabilities({Capabilities.APM_TRACING_CUSTOM_TAGS})


@scenarios.parametric
@features.dynamic_configuration
@features.adaptive_sampling
class TestDynamicConfigSamplingRules:
    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_capability_tracing_sample_rules(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Ensure the RC request contains the trace sampling rules capability."""
        assert test_library.is_alive(), "library container is not alive"
        test_agent.assert_rc_capabilities({Capabilities.APM_TRACING_SAMPLE_RULES})

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": ENV_SAMPLING_RULE_RATE, "service": "*"}]),
            }
        ],
    )
    def test_trace_sampling_rules_override_env(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """The RC sampling rules should override the environment variable and decision maker is set appropriately.

        When RC is unset, the environment variable should be used.
        """
        rc_sampling_rule_rate_customer = 0.8
        rc_sampling_rule_rate_dynamic = 0.4
        assert rc_sampling_rule_rate_customer != ENV_SAMPLING_RULE_RATE
        assert rc_sampling_rule_rate_dynamic != ENV_SAMPLING_RULE_RATE
        assert rc_sampling_rule_rate_customer != DEFAULT_SAMPLE_RATE
        assert rc_sampling_rule_rate_dynamic != DEFAULT_SAMPLE_RATE

        trace = get_sampled_trace(test_library, test_agent, service="", name="env_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        # Make sure `_dd.p.dm` is set to "-3" (i.e., local RULE_RATE)
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        # The "-" is a separating hyphen, not a minus sign.
        assert span["meta"]["_dd.p.dm"] == "-3"

        # Create a remote config entry with two rules at different sample rates.
        set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rules": [
                    {
                        "sample_rate": rc_sampling_rule_rate_customer,
                        "service": TEST_SERVICE,
                        "resource": "*",
                        "provenance": "customer",
                    },
                    {
                        "sample_rate": rc_sampling_rule_rate_dynamic,
                        "service": "*",
                        "resource": "*",
                        "provenance": "dynamic",
                    },
                ]
            },
        )

        trace = get_sampled_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name")
        assert_sampling_rate(trace, rc_sampling_rule_rate_customer)
        # Make sure `_dd.p.dm` is set to "-11" (i.e., remote user rule)
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-11"

        trace = get_sampled_trace(test_library, test_agent, service="other_service", name="op_name")
        assert_sampling_rate(trace, rc_sampling_rule_rate_dynamic)
        # Make sure `_dd.p.dm` is set to "-12" (i.e., remote dynamic rule)
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-12"

        # Unset the RC sample rate to ensure the previous setting is reapplied.
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rules": None})
        trace = get_sampled_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name")
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        # Make sure `_dd.p.dm` is restored to "-3"
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_trace_sampling_rules_override_rate(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """The RC sampling rules should override the RC sampling rate."""
        rc_sampling_rule_rate_customer = 0.8
        rc_sampling_rate = 0.9
        assert rc_sampling_rule_rate_customer != DEFAULT_SAMPLE_RATE
        assert rc_sampling_rate != DEFAULT_SAMPLE_RATE

        # Create an initial trace to assert the default sampling settings.
        trace = send_and_wait_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

        set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rate": rc_sampling_rate,
                "tracing_sampling_rules": [
                    {
                        "sample_rate": rc_sampling_rule_rate_customer,
                        "service": TEST_SERVICE,
                        "resource": "*",
                        "provenance": "customer",
                    }
                ],
            },
        )

        # trace/span matching the rule gets applied the rule's rate
        trace = get_sampled_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name")
        assert_sampling_rate(trace, rc_sampling_rule_rate_customer)
        # Make sure `_dd.p.dm` is set to "-11" (i.e., remote user rule)
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-11"

        # trace/span not matching the rule gets applied the RC global rate
        trace = get_sampled_trace(test_library, test_agent, service="other_service", name="op_name")
        assert_sampling_rate(trace, rc_sampling_rate)
        # `_dd.p.dm` is set to "-3" (rule rate, this is the legacy behavior)
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

        # Unset RC to ensure local settings
        set_and_wait_rc(test_agent, config_overrides={"tracing_sampling_rules": None})
        trace = get_sampled_trace(test_library, test_agent, service="other_service", name="op_name")
        assert_sampling_rate(trace, DEFAULT_SAMPLE_RATE)

    @parametrize(
        "library_env",
        [
            {
                **DEFAULT_ENVVARS,
                "DD_TRACE_SAMPLING_RULES": json.dumps([{"sample_rate": ENV_SAMPLING_RULE_RATE, "service": "*"}]),
            }
        ],
    )
    def test_trace_sampling_rules_with_tags(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """RC sampling rules with tags should match/skip spans with/without corresponding tag values.

        When a sampling rule contains a tag clause/pattern, it should be used to match against a trace/span.
        If span does not contain the tag or the tag value matches the pattern, sampling decisions are made using the corresponding rule rate.
        Otherwise, sampling decision is made using the next precedence mechanism (remote global rate in our test case).
        """
        rc_sampling_tags_rule_rate = 0.8
        rc_sampling_rate = 0.3
        rc_sampling_adaptive_rate = 0.1
        assert rc_sampling_tags_rule_rate != ENV_SAMPLING_RULE_RATE
        assert rc_sampling_rate != ENV_SAMPLING_RULE_RATE
        assert rc_sampling_adaptive_rate != ENV_SAMPLING_RULE_RATE

        trace = get_sampled_trace(
            test_library,
            test_agent,
            service=TEST_SERVICE,
            name="op_name",
            tags=[("tag-a", "tag-a-val")],
        )
        assert_sampling_rate(trace, ENV_SAMPLING_RULE_RATE)
        # Make sure `_dd.p.dm` is set to "-3" (i.e., local RULE_RATE)
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        # The "-" is a separating hyphen, not a minus sign.
        assert span["meta"]["_dd.p.dm"] == "-3"

        # Create a remote config entry with two rules at different sample rates.
        rc_state = set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rate": rc_sampling_rate,
                "tracing_sampling_rules": [
                    {
                        "sample_rate": rc_sampling_tags_rule_rate,
                        "service": TEST_SERVICE,
                        "resource": "*",
                        "tags": [{"key": "tag-a", "value_glob": "tag-a-val*"}],
                        "provenance": "customer",
                    },
                ],
            },
        )

        # Keep a reference on the RC config ID
        config_id = rc_state["id"]

        # A span with matching tag and value. The remote matching tag rule should apply.
        trace = get_sampled_trace(
            test_library,
            test_agent,
            service=TEST_SERVICE,
            name="op_name",
            tags=[("tag-a", "tag-a-val")],
        )
        assert_sampling_rate(trace, rc_sampling_tags_rule_rate)
        # Make sure `_dd.p.dm` is set to "-11" (i.e., remote user RULE_RATE)
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        # The "-" is a separating hyphen, not a minus sign.
        assert span["meta"]["_dd.p.dm"] == "-11"

        # A span with the tag but value does not match. Remote global rate should apply.
        trace = get_sampled_trace(
            test_library,
            test_agent,
            service=TEST_SERVICE,
            name="op_name",
            tags=[("tag-a", "NOT-tag-a-val")],
        )
        assert_sampling_rate(trace, rc_sampling_rate)
        # Make sure `_dd.p.dm` is set to "-3"
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

        # A different tag key, value does not matter. Remote global rate should apply.
        trace = get_sampled_trace(
            test_library,
            test_agent,
            service=TEST_SERVICE,
            name="op_name",
            tags=[("not-tag-a", "tag-a-val")],
        )
        assert_sampling_rate(trace, rc_sampling_rate)
        # Make sure `_dd.p.dm` is set to "-3"
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

        # A span without the tag. Remote global rate should apply.
        trace = get_sampled_trace(test_library, test_agent, service=TEST_SERVICE, name="op_name", tags=[])
        assert_sampling_rate(trace, rc_sampling_rate)
        # Make sure `_dd.p.dm` is set to "-3"
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-3"

        # RC config using dynamic sampling
        set_and_wait_rc(
            test_agent,
            config_id=config_id,
            config_overrides={
                "dynamic_sampling_enabled": "true",
                "tracing_sampling_rules": [
                    {
                        "sample_rate": rc_sampling_tags_rule_rate,
                        "service": TEST_SERVICE,
                        "resource": "*",
                        "tags": [{"key": "tag-a", "value_glob": "tag-a-val*"}],
                        "provenance": "customer",
                    },
                    {
                        "sample_rate": rc_sampling_adaptive_rate,
                        "service": "*",
                        "resource": "*",
                        "provenance": "dynamic",
                    },
                ],
            },
        )

        # A span with non-matching tags. Adaptive rate should apply.
        trace = get_sampled_trace(
            test_library,
            test_agent,
            service=TEST_SERVICE,
            name="op_name",
            tags=[("tag-a", "NOT-tag-a-val")],
        )
        assert_sampling_rate(trace, rc_sampling_adaptive_rate)
        # Make sure `_dd.p.dm` is set to "-12" (i.e., remote adaptive/dynamic sampling RULE_RATE)
        span = find_first_span_in_trace_payload(trace)
        assert "_dd.p.dm" in span["meta"]
        assert span["meta"]["_dd.p.dm"] == "-12"

    @parametrize("library_env", [{**DEFAULT_ENVVARS}])
    def test_remote_sampling_rules_retention(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Only the last set of sampling rules should be applied"""
        rc_state = set_and_wait_rc(
            test_agent,
            config_overrides={
                "tracing_sampling_rules": [
                    {
                        "service": "svc*",
                        "resource": "*",
                        "sample_rate": 0.5,
                        "provenance": "customer",
                    }
                ],
            },
        )

        # Keep a reference on the RC config ID
        config_id = rc_state["id"]

        set_and_wait_rc(
            test_agent,
            config_id=config_id,
            config_overrides={
                "tracing_sampling_rules": [
                    {
                        "service": "foo*",
                        "resource": "*",
                        "sample_rate": 0.1,
                        "provenance": "customer",
                    }
                ],
            },
        )

        trace = send_and_wait_trace(test_library, test_agent, name="test", service="foo")
        assert_sampling_rate(trace, 0.1)

        trace = send_and_wait_trace(test_library, test_agent, name="test2", service="svc")
        assert_sampling_rate(trace, 1)
