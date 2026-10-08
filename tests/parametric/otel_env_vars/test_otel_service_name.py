from typing import Any

from utils import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.otel_env_vars.utils import generate_default_counter_data_point
from tests.parametric.utils import find_log_components
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel
from utils.docker_fixtures.spec.trace import find_span_in_traces


def _service_name(test_agent: TestAgentAPI, test_library: APMLibrary) -> str:
    with test_library, test_library.dd_start_span("operation") as root:
        pass

    traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
    span = find_span_in_traces(traces, root.trace_id, root.span_id)
    value = span["service"]
    assert isinstance(value, str)
    return value


def _signal_service_name_cases(signal: str, *, resource_precedence: bool | None = None) -> pytest.MarkDecorator:
    environment = {
        "DD_TRACE_OTEL_ENABLED": "true",
        "DD_TRACE_DEBUG": None,
        "DD_LOGS_OTEL_ENABLED": "true" if signal == "logs" else "false",
        "DD_METRICS_OTEL_ENABLED": "true" if signal == "metrics" else "false",
        "DD_RUNTIME_METRICS_ENABLED": "false",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
        "OTEL_METRIC_EXPORT_INTERVAL": "60000",
        "CORECLR_ENABLE_PROFILING": "1",
        "OTEL_SERVICE_NAME": "otel-service",
    }
    cases = [
        pytest.param(
            {**environment, "DD_SERVICE": None, "OTEL_RESOURCE_ATTRIBUTES": None},
            "otel-service",
            id="otel-only",
        ),
        pytest.param(
            {**environment, "DD_SERVICE": None, "OTEL_RESOURCE_ATTRIBUTES": "service.name=resource-service"},
            "otel-service",
            id="otel-over-resource",
        ),
        pytest.param(
            {
                **environment,
                "DD_SERVICE": "datadog-service",
                "OTEL_RESOURCE_ATTRIBUTES": "service.name=resource-service",
            },
            "datadog-service",
            id="datadog-over-otel-and-resource",
        ),
    ]
    if resource_precedence is not None:
        cases = [case for case in cases if (case.id == "otel-over-resource") == resource_precedence]
    return pytest.mark.parametrize(("library_env", "expected"), cases)


def _assert_resource_service_name(resource: dict[str, Any], expected: str) -> None:
    attributes = {attribute["key"]: attribute["value"] for attribute in resource.get("attributes", [])}
    assert attributes.get("service.name") == {"string_value": expected}, attributes


def _assert_log_service_name(test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
    name = "otel_service_name"
    with test_library as library:
        library.create_logger(name, LogLevel.INFO)
        library.write_log(name, LogLevel.INFO, name)

    record, _, resource_log = find_log_components(test_agent.wait_for_num_log_payloads(1), name, name)
    assert record is not None, "The test log record was not exported"
    assert resource_log is not None
    _assert_resource_service_name(resource_log["resource"], expected)


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
            "OTEL_SERVICE_NAME": None,
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

DEFAULT_VALUE = [
    pytest.param(
        {
            "DD_SERVICE": None,
            "OTEL_RESOURCE_ATTRIBUTES": None,
            "OTEL_SERVICE_NAME": None,
        },
        id="default",
    ),
]


@scenarios.parametric
@features.otel_service_name
class Test_OTEL_SERVICE_NAME:
    @_signal_service_name_cases("logs", resource_precedence=False)
    def test_logs_service_name(self, test_agent: TestAgentAPI, test_library: APMLibrary, *, expected: str) -> None:
        """OTEL_SERVICE_NAME sets log resource service.name unless DD_SERVICE is set."""
        _assert_log_service_name(test_agent, test_library, expected)

    @_signal_service_name_cases("logs", resource_precedence=True)
    def test_logs_service_name_takes_precedence(
        self, test_agent: TestAgentAPI, test_library: APMLibrary, *, expected: str
    ) -> None:
        """OTEL_SERVICE_NAME overrides service.name in OTEL_RESOURCE_ATTRIBUTES for logs."""
        _assert_log_service_name(test_agent, test_library, expected)

    @_signal_service_name_cases("traces")
    def test_traces_service_name(self, test_agent: TestAgentAPI, test_library: APMLibrary, *, expected: str) -> None:
        """OTEL_SERVICE_NAME applies to spans created through the OpenTelemetry API."""
        with test_library, test_library.otel_start_span("otel_service_name") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        span = find_span_in_traces(traces, root.trace_id, root.span_id)
        assert span["service"] == expected

    @_signal_service_name_cases("metrics")
    def test_metrics_service_name(self, test_agent: TestAgentAPI, test_library: APMLibrary, *, expected: str) -> None:
        """OTEL_SERVICE_NAME sets metric resource service.name and overrides resource attributes."""
        name = "otel_service_name"
        with test_library as library:
            generate_default_counter_data_point(library, name)

        resources = [
            resource_metric["resource"]
            for payload in test_agent.wait_for_num_otlp_metrics(1)
            for resource_metric in payload["resource_metrics"]
            if any(
                metric["name"] == name
                for scope_metric in resource_metric.get("scope_metrics", [])
                for metric in scope_metric.get("metrics", [])
            )
        ]
        assert resources, "The test metric was not exported"
        for resource in resources:
            _assert_resource_service_name(resource, expected)

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

    @pytest.mark.parametrize("library_env", DEFAULT_VALUE)
    def test_default_follows_otel_spec(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        assert _service_name(test_agent, test_library).startswith("unknown_service")

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
