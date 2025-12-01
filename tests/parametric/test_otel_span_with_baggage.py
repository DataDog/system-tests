import pytest

from utils import scenarios, features
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary

# this global mark applies to all tests in this file.
#   DD_TRACE_OTEL_ENABLED=true is required in some tracers (.NET, Python?)
#   CORECLR_ENABLE_PROFILING=1 is required in .NET to enable auto-instrumentation
pytestmark = pytest.mark.parametrize(
    "library_env", [{"DD_TRACE_OTEL_ENABLED": "true", "CORECLR_ENABLE_PROFILING": "1"}]
)


@scenarios.parametric
@features.open_tracing_api
class Test_Otel_Span_With_Baggage:
    def test_otel_span_with_baggage_headers(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with test_library, test_library.otel_start_span(name="otel-baggage-inject") as otel_span:
            value = test_library.otel_set_baggage(otel_span.span_id, "foo", "bar")
            assert value == "bar"
