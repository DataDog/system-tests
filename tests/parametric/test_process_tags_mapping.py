"""Parametric system test for DD_PROCESS_TAGS_MAPPING.

Verifies the contract introduced by the RFC "Infer Process Tags from User Configuration":
the configuration ``DD_PROCESS_TAGS_MAPPING`` accepts a comma-separated list of
``{source}config_key:process_tag_key`` mappings and emits matching process tags
(stored in ``_dd.tags.process``) only when the source is recognised, the key exists
and the value is non-empty.

Currently the feature is tailored to dd-trace-java; other tracers are gated as
``missing_feature`` in their manifests until a follow-up RFC extends the contract.
"""

import pytest

from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import find_root_span, find_trace

from .conftest import APMLibrary


parametrize = pytest.mark.parametrize


@scenarios.parametric
@features.process_tags
class Test_ProcessTagsMapping:
    """End-to-end validation of DD_PROCESS_TAGS_MAPPING.

    Each test sets ``DD_PROCESS_TAGS_MAPPING`` (and any backing env vars) via
    ``library_env`` and inspects the ``_dd.tags.process`` meta field of the
    root span emitted by the parametric library harness.
    """

    @parametrize(
        "library_env",
        [
            {
                "TEST_ENV_KEY": "test_env_value",
                "DD_PROCESS_TAGS_MAPPING": "{env}TEST_ENV_KEY:custom_tag",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
            }
        ],
    )
    def test_env_source_emits_tag(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """A single valid ``{env}`` mapping resolves to ``process_tag_key:value``.

        Covers TS-019, TS-030, TS-035 from the RFC test plan.
        """
        with test_library, test_library.dd_start_span("operation") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, root.trace_id)
        span = find_root_span(trace)
        assert span is not None
        process_tags = span["meta"]["_dd.tags.process"]
        assert "custom_tag:test_env_value" in process_tags, (
            f"Expected mapped tag 'custom_tag:test_env_value' in process tags, got: {process_tags}"
        )

    @parametrize(
        "library_env",
        [
            {
                "DD_PROCESS_TAGS_MAPPING": "{env}NOT_SET_KEY:missing_tag",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
            }
        ],
    )
    def test_missing_key_no_emission(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """When the referenced env var does not exist, no mapped tag is emitted.

        Covers TS-024, TS-032 from the RFC test plan.
        """
        with test_library, test_library.dd_start_span("operation") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, root.trace_id)
        span = find_root_span(trace)
        assert span is not None
        process_tags = span["meta"].get("_dd.tags.process", "")
        assert "missing_tag:" not in process_tags, (
            f"Expected no 'missing_tag:' in process tags when key is unset, got: {process_tags}"
        )

    @parametrize(
        "library_env",
        [
            {
                "EMPTY_KEY": "",
                "DD_PROCESS_TAGS_MAPPING": "{env}EMPTY_KEY:empty_tag",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
            }
        ],
    )
    def test_empty_value_no_emission(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """When the referenced env var is set but empty, no mapped tag is emitted.

        Covers TS-026, TS-033 from the RFC test plan.
        """
        with test_library, test_library.dd_start_span("operation") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, root.trace_id)
        span = find_root_span(trace)
        assert span is not None
        process_tags = span["meta"].get("_dd.tags.process", "")
        assert "empty_tag:" not in process_tags, (
            f"Expected no 'empty_tag:' in process tags when value is empty, got: {process_tags}"
        )

    @parametrize(
        "library_env",
        [
            {
                "K1": "v1",
                "K2": "v2",
                "DD_PROCESS_TAGS_MAPPING": "{env}K1:collision_tag,{env}K2:collision_tag",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
            }
        ],
    )
    def test_last_wins_both_valid(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """When two mappings emit the same process_tag_key, the last one wins.

        Covers TS-045, TS-048 from the RFC test plan.
        """
        with test_library, test_library.dd_start_span("operation") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, root.trace_id)
        span = find_root_span(trace)
        assert span is not None
        process_tags = span["meta"]["_dd.tags.process"]
        assert "collision_tag:v2" in process_tags, (
            f"Expected last-wins tag 'collision_tag:v2' in process tags, got: {process_tags}"
        )
        assert "collision_tag:v1" not in process_tags, (
            f"Expected previous mapping value 'collision_tag:v1' to be overridden, got: {process_tags}"
        )

    @parametrize(
        "library_env",
        [
            {
                "EXPLICIT_KEY": "explicit_value",
                "IMPLICIT_KEY": "implicit_value",
                "DD_PROCESS_TAGS_MAPPING": "{env}EXPLICIT_KEY:explicit_tag",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
            }
        ],
    )
    def test_security_explicit_only(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """Only env vars listed in DD_PROCESS_TAGS_MAPPING are exposed as process tags.

        Covers TS-056, TS-057 from the RFC test plan.
        """
        with test_library, test_library.dd_start_span("operation") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, root.trace_id)
        span = find_root_span(trace)
        assert span is not None
        process_tags = span["meta"]["_dd.tags.process"]
        assert "explicit_tag:explicit_value" in process_tags, (
            f"Expected explicitly mapped tag in process tags, got: {process_tags}"
        )
        assert "implicit_value" not in process_tags, (
            f"Expected non-listed env var value 'implicit_value' to NOT be exposed, got: {process_tags}"
        )

    @parametrize(
        "library_env",
        [
            {
                "DD_PROCESS_TAGS_MAPPING": "{invalid}SOME_KEY:bad_tag",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
                "SOME_KEY": "some_value",
            }
        ],
    )
    def test_unrecognised_source_no_emission(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        """An unrecognised source (e.g. ``{invalid}``) is rejected gracefully.

        Covers TS-009, TS-031 from the RFC test plan.
        """
        with test_library, test_library.dd_start_span("operation") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, root.trace_id)
        span = find_root_span(trace)
        assert span is not None
        process_tags = span["meta"].get("_dd.tags.process", "")
        assert "bad_tag:" not in process_tags, f"Expected no 'bad_tag:' from unrecognised source, got: {process_tags}"
