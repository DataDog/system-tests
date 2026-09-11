import pytest

from tests.parametric.conftest import APMLibrary, nodejs_telemetry_value
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


SAMPLER_ENV = {
    "DD_TRACE_OTEL_ENABLED": "true",
    "DD_TRACE_SAMPLE_RATE": None,
    "DD_TRACE_SAMPLING_RULES": None,
}

JAEGER_REMOTE_ARGUMENT = "endpoint=http://localhost:14250,pollingIntervalMs=5000,initialSamplingRate=0.25"

STABLE_VALUES = [
    pytest.param(
        {**SAMPLER_ENV, "OTEL_TRACES_SAMPLER": "always_on"},
        1.0,
        id="always_on",
    ),
    pytest.param(
        {**SAMPLER_ENV, "OTEL_TRACES_SAMPLER": "always_off"},
        0.0,
        id="always_off",
    ),
    pytest.param(
        {
            **SAMPLER_ENV,
            "OTEL_TRACES_SAMPLER": "traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "0.25",
        },
        0.25,
        id="traceidratio",
    ),
    pytest.param(
        {**SAMPLER_ENV, "OTEL_TRACES_SAMPLER": "parentbased_always_on"},
        1.0,
        id="parentbased_always_on",
    ),
    pytest.param(
        {**SAMPLER_ENV, "OTEL_TRACES_SAMPLER": "parentbased_always_off"},
        0.0,
        id="parentbased_always_off",
    ),
    pytest.param(
        {
            **SAMPLER_ENV,
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": "0.25",
        },
        0.25,
        id="parentbased_traceidratio",
    ),
    pytest.param(
        {
            **SAMPLER_ENV,
            "OTEL_TRACES_SAMPLER": "jaeger_remote",
            "OTEL_TRACES_SAMPLER_ARG": JAEGER_REMOTE_ARGUMENT,
        },
        0.25,
        id="jaeger_remote",
    ),
    pytest.param(
        {
            **SAMPLER_ENV,
            "OTEL_TRACES_SAMPLER": "parentbased_jaeger_remote",
            "OTEL_TRACES_SAMPLER_ARG": JAEGER_REMOTE_ARGUMENT,
        },
        0.25,
        id="parentbased_jaeger_remote",
    ),
]

UNSET_VALUE = [
    pytest.param(
        {
            **SAMPLER_ENV,
            "OTEL_TRACES_SAMPLER": None,
            "OTEL_TRACES_SAMPLER_ARG": None,
        },
        id="unset",
    )
]

EMPTY_VALUE = [
    pytest.param(
        {
            **SAMPLER_ENV,
            "OTEL_TRACES_SAMPLER": "",
            "OTEL_TRACES_SAMPLER_ARG": None,
        },
        id="empty",
    )
]

INVALID_VALUE = [
    pytest.param(
        {
            **SAMPLER_ENV,
            "OTEL_TRACES_SAMPLER": "invalid",
            "OTEL_TRACES_SAMPLER_ARG": None,
        },
        id="invalid",
    )
]

THIRD_PARTY_VALUES = [
    pytest.param(
        {**SAMPLER_ENV, "OTEL_TRACES_SAMPLER": "xray"},
        id="xray",
    )
]

XRAY_DECISION_COUNT = 32


def _sample_rate(test_agent: TestAgentAPI, library: APMLibrary) -> float:
    if library.lang == "nodejs":
        value = nodejs_telemetry_value(test_agent, "dd_trace_sample_rate")
    else:
        value = library.config()["dd_trace_sample_rate"]

    assert isinstance(value, (float, str, bool, int))
    return float(value)


@scenarios.parametric
@features.otel_traces_sampler
class Test_OTEL_TRACES_SAMPLER:
    @pytest.mark.parametrize(("library_env", "expected"), STABLE_VALUES)
    def test_stable_values(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected: float,
    ) -> None:
        with test_library as library:
            assert _sample_rate(test_agent, library) == expected

    @pytest.mark.parametrize(
        "library_env",
        [pytest.param({**SAMPLER_ENV, "OTEL_TRACES_SAMPLER": "always_on"}, id="always_on")],
    )
    def test_dd_trace_sample_ignore_parent_true(self, test_library: APMLibrary) -> None:
        with test_library as library:
            config = library.config()
        assert config["dd_trace_sample_ignore_parent"] == "true"

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {**SAMPLER_ENV, "OTEL_TRACES_SAMPLER": "parentbased_always_off"},
                id="parentbased_always_off",
            )
        ],
    )
    def test_dd_trace_sample_ignore_parent_false(self, test_library: APMLibrary) -> None:
        with test_library as library:
            config = library.config()
        assert config["dd_trace_sample_ignore_parent"] == "false"

    @pytest.mark.parametrize("library_env", UNSET_VALUE)
    def test_default_matches_specification(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            assert _sample_rate(test_agent, library) == 1.0

    @pytest.mark.parametrize("library_env", EMPTY_VALUE)
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            assert _sample_rate(test_agent, library) == 1.0

    @pytest.mark.parametrize("library_env", INVALID_VALUE)
    def test_invalid_value_is_ignored(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            assert _sample_rate(test_agent, library) == 1.0

    @pytest.mark.parametrize("library_env", THIRD_PARTY_VALUES)
    def test_third_party_values(self, test_library: APMLibrary) -> None:
        decisions = []
        with test_library as library:
            for index in range(XRAY_DECISION_COUNT):
                with library.otel_start_span(f"xray-{index}") as span:
                    decisions.append(span.is_recording())

        assert any(decisions)
        assert not all(decisions)
