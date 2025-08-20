import pytest

from utils import scenarios, features


@features.otel_logs_enabled
@scenarios.parametric
class Test_Otel_Logs:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_LOGS_OTEL_ENABLED": "true",
            }
        ],
    )
    def test_otel_logs_enabled(self, test_agent, test_library):
        with test_library as library:
            library.log_generate("Test log message", "INFO", "test_logger", 0)

        import time

        time.sleep(10000)
        logs = test_agent.wait_for_num_logs(1)
        assert len(logs) == 1
