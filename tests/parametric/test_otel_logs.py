import pytest

from utils import scenarios, features
from utils.parametric._library_client import LogLevel


@features.otel_logs_enabled
@scenarios.parametric
class Test_Otel_Logs:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
            }
        ],
    )
    def test_otel_logs_enabled(self, test_agent, test_library):
        with test_library as library:
            library.write_log("Test log message", LogLevel.INFO, "test_logger", 0)

        logs = test_agent.wait_for_num_logs(1)
        assert len(logs) == 1
