import pytest

from tests.parametric.conftest import APMLibrary, nodejs_telemetry_value
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


def _trace_sample_rate(test_agent: TestAgentAPI, test_library: APMLibrary) -> float:
    with test_library as library:
        if library.lang == "nodejs":
            value = nodejs_telemetry_value(test_agent, "dd_trace_sample_rate")
        else:
            value = library.config()["dd_trace_sample_rate"]

    assert isinstance(value, (float, int, str))
    return float(value)


VALID_RATIO_ARGUMENTS = [
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "0",
        },
        0.0,
        id="lower-boundary",
    ),
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "0.1",
        },
        0.1,
        id="0.1",
    ),
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "0.25",
        },
        0.25,
        id="representative",
    ),
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "1",
        },
        1.0,
        id="upper-boundary",
    ),
]

INVALID_RATIO_ARGUMENTS = [
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "-0.1",
        },
        id="below-range",
    ),
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "1.1",
        },
        id="above-range",
    ),
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "not-a-number",
        },
        id="not-a-number",
    ),
]

UNSET_VALUE = [
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": None,
        },
        id="unset",
    )
]

EMPTY_VALUE = [
    pytest.param(
        {
            "DD_TRACE_SAMPLE_RATE": None,
            "DD_TRACE_SAMPLING_RULES": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "",
        },
        id="empty",
    )
]


@scenarios.parametric
@features.otel_traces_sampler_arg
class Test_OTEL_TRACES_SAMPLER_ARG:
    @pytest.mark.parametrize(("library_env", "expected"), VALID_RATIO_ARGUMENTS)
    def test_stable_values(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected: float,
    ) -> None:
        assert _trace_sample_rate(test_agent, test_library) == expected

    @pytest.mark.parametrize("library_env", INVALID_RATIO_ARGUMENTS)
    def test_invalid_values_are_ignored(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        assert _trace_sample_rate(test_agent, test_library) == 1.0

    @pytest.mark.parametrize("library_env", UNSET_VALUE)
    def test_default_matches_specification(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        assert _trace_sample_rate(test_agent, test_library) == 1.0

    @pytest.mark.parametrize("library_env", EMPTY_VALUE)
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        assert _trace_sample_rate(test_agent, test_library) == 1.0
