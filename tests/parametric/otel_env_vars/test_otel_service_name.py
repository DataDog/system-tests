import pytest

from tests.parametric.conftest import APMLibrary, nodejs_telemetry_value
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


def _service_name(test_agent: TestAgentAPI, library: APMLibrary) -> str:
    if library.lang == "nodejs":
        value = nodejs_telemetry_value(test_agent, "dd_service")
    else:
        value = library.config()["dd_service"]

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
        with test_library as library:
            assert _service_name(test_agent, library) == expected

    @pytest.mark.parametrize("library_env", UNSET_VALUE)
    def test_default_matches_specification(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            assert _service_name(test_agent, library) == "resource-service"

    @pytest.mark.parametrize("library_env", EMPTY_VALUE)
    def test_empty_is_treated_as_unset(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            assert _service_name(test_agent, library) == "resource-service"

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
        with test_library as library:
            assert _service_name(test_agent, library) == "otel-service"

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
        with test_library as library:
            assert _service_name(test_agent, library) == "datadog-service"
