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
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                "DD_TRACE_DEBUG": "false",
            },
            # Not supported yet
            # {
            #     "DD_LOGS_OTEL_ENABLED": "true",
            #     "OTEL_EXPORTER_OTLP_PROTOCOL": "http/json",
            #     "DD_TRACE_DEBUG": "false",
            # },
            {
                "DD_LOGS_OTEL_ENABLED": "true",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "DD_TRACE_DEBUG": "false",
            },
        ],
        "",
    )
    def test_otel_logs_exporter_otlp_protocol(self, test_agent, test_library):
        log_message = "Test log message"
        logger_name = "test_logger"
        with test_library as library:
            library.write_log(log_message, LogLevel.INFO, logger_name, 0)

        expected_log = None
        log_payloads = test_agent.wait_for_num_log_payloads(1)
        for payload in log_payloads:
            resource_logs = payload["resource_logs"]
            for resource_log in resource_logs:
                for scope_log in resource_log["scope_logs"]:
                    if scope_log["scope"] and scope_log["scope"]["name"] == logger_name:
                        for log_recrod in scope_log["log_records"]:
                            if log_recrod["body"]["string_value"] == log_message:
                                expected_log = log_recrod
        assert expected_log is not None
