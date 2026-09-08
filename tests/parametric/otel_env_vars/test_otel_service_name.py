import pytest

from tests.parametric.conftest import APMLibrary
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import find_span_in_traces


def _service_name(test_agent: TestAgentAPI, test_library: APMLibrary) -> str:
    with test_library, test_library.dd_start_span("operation") as root:
        pass

    traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
    span = find_span_in_traces(traces, root.trace_id, root.span_id)
    value = span["service"]
    assert isinstance(value, str)
    return value


SERVICE_NAMES = [
    pytest.param(
        {
            "DD_SERVICE": None,
            "OTEL_RESOURCE_ATTRIBUTES": None,
            "OTEL_SERVICE_NAME": "checkout-service",
        },
        "checkout-service",
        id="checkout-service",
    ),
    pytest.param(
        {
            "DD_SERVICE": None,
            "OTEL_RESOURCE_ATTRIBUTES": None,
            "OTEL_SERVICE_NAME": "checkout.worker/v2",
        },
        "checkout.worker/v2",
        id="punctuation",
    ),
]

UNSET_VALUE = [
    pytest.param(
        {
            "DD_SERVICE": None,
            "OTEL_RESOURCE_ATTRIBUTES": "service.name=resource-service",
        },
        id="unset",
    )
]

EMPTY_VALUE = [
    pytest.param(
        {
            "DD_SERVICE": None,
            "OTEL_RESOURCE_ATTRIBUTES": "service.name=resource-service",
            "OTEL_SERVICE_NAME": "",
        },
        id="empty",
    ),
]


@scenarios.parametric
@features.otel_service_name
class Test_OTEL_SERVICE_NAME:
    @pytest.mark.parametrize(("library_env", "expected"), SERVICE_NAMES)
    def test_stable_values(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected: str,
    ) -> None:
        assert _service_name(test_agent, test_library) == expected

    @pytest.mark.parametrize("library_env", UNSET_VALUE)
    def test_default_matches_specification(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        assert _service_name(test_agent, test_library) == "resource-service"

    @pytest.mark.parametrize("library_env", EMPTY_VALUE)
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        assert _service_name(test_agent, test_library) == "resource-service"

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {
                    "DD_SERVICE": None,
                    "OTEL_RESOURCE_ATTRIBUTES": "service.name=resource-service",
                    "OTEL_SERVICE_NAME": "otel-service",
                },
                id="otel-over-resource",
            )
        ],
    )
    def test_otel_service_name_takes_precedence(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        assert _service_name(test_agent, test_library) == "otel-service"

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {
                    "DD_SERVICE": "datadog-service",
                    "OTEL_SERVICE_NAME": "otel-service",
                },
                id="datadog-over-otel",
            )
        ],
    )
    def test_datadog_configuration_takes_precedence(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        assert _service_name(test_agent, test_library) == "datadog-service"
