"""Prove OTEL_EXPORTER_OTLP_COMPRESSION through the encoding of an emitted OTLP request."""

import pytest

from tests.parametric.conftest import APMLibrary
from tests.parametric.test_otel_metrics import generate_default_counter_data_point
from utils import features, scenarios
from utils.docker_fixtures import TestAgentAPI


# Pin HTTP/protobuf because compression is asserted through Content-Encoding
# on the original HTTP request. Some SDKs default to gRPC; routing to its
# collector works, but forwarded HTTP requests do not expose gRPC compression.
@pytest.fixture
def library_env(compression_env: dict[str, str]) -> dict[str, str]:
    return {
        "DD_METRICS_OTEL_ENABLED": "true",
        "OTEL_EXPORTER_OTLP_METRICS_PROTOCOL": "http/protobuf",
        **compression_env,
    }


@scenarios.parametric
@features.otel_exporter_otlp_compression
class Test_OTEL_EXPORTER_OTLP_COMPRESSION:
    @pytest.mark.parametrize(
        ("compression_env", "expected"),
        [
            pytest.param({"OTEL_EXPORTER_OTLP_COMPRESSION": "gzip"}, "gzip", id="gzip"),
            pytest.param({"OTEL_EXPORTER_OTLP_COMPRESSION": "none"}, "none", id="none"),
        ],
    )
    def test_stable_values(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        self._assert_compression(test_agent, test_library, expected)

    @pytest.mark.parametrize("compression_env", [pytest.param({}, id="unset")])
    def test_default(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        # The specification permits SDK-specific defaults; Java and Python default to no compression.
        self._assert_compression(test_agent, test_library, "none")

    @pytest.mark.parametrize("compression_env", [pytest.param({"OTEL_EXPORTER_OTLP_COMPRESSION": ""}, id="empty")])
    def test_empty(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_compression(test_agent, test_library, "none")

    @pytest.mark.parametrize(
        "compression_env", [pytest.param({"OTEL_EXPORTER_OTLP_COMPRESSION": "not-a-compression"}, id="invalid")]
    )
    def test_invalid(self, test_agent: TestAgentAPI, test_library: APMLibrary) -> None:
        self._assert_compression(test_agent, test_library, "none")

    def _assert_compression(self, test_agent: TestAgentAPI, test_library: APMLibrary, expected: str) -> None:
        # A single exported artifact proves that the effective compressor is in use.
        with test_library as library:
            generate_default_counter_data_point(library, "compression_probe")

        test_agent.wait_for_num_otlp_metrics(1)
        requests = [request for request in test_agent.otlp_requests() if request["url"].endswith("/v1/metrics")]
        assert requests, "No OTLP metrics request was captured"
        for request in requests:
            headers = {name.lower(): value.lower() for name, value in request["headers"].items()}
            encoding = headers.get("content-encoding", "identity")
            if expected == "gzip":
                assert encoding == "gzip", headers
            else:
                assert encoding in ("identity", ""), headers
