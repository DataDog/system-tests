from typing import Final

from tests.parametric.conftest import APMLibrary
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.parametric import LogLevel


BLRP_LIBRARY_ENV: Final = {
    "DD_LOGS_OTEL_ENABLED": "true",
    "DD_LOGS_OTEL_INTERVAL": None,
    "DD_LOGS_OTEL_TIMEOUT": None,
    "DD_LOGS_OTEL_QUEUE_SIZE": None,
    "DD_LOGS_OTEL_BATCH_SIZE": None,
    "OTEL_BLRP_SCHEDULE_DELAY": None,
    "OTEL_BLRP_EXPORT_TIMEOUT": None,
    "OTEL_BLRP_MAX_QUEUE_SIZE": None,
    "OTEL_BLRP_MAX_EXPORT_BATCH_SIZE": None,
}

JAVA_TELEMETRY_NAMES: Final = {
    "OTEL_BLRP_SCHEDULE_DELAY": "DD_LOGS_OTEL_INTERVAL",
    "OTEL_BLRP_EXPORT_TIMEOUT": "DD_LOGS_OTEL_TIMEOUT",
    "OTEL_BLRP_MAX_QUEUE_SIZE": "DD_LOGS_OTEL_QUEUE_SIZE",
    "OTEL_BLRP_MAX_EXPORT_BATCH_SIZE": "DD_LOGS_OTEL_BATCH_SIZE",
}

TEST_LOGGER_NAME: Final = "blrp_configuration"
TEST_LOG_MESSAGE: Final = "blrp_configuration"


def assert_blrp_configuration(
    test_agent: TestAgentAPI,
    test_library: APMLibrary,
    variable_name: str,
    expected_value: int,
) -> None:
    with test_library as library:
        library.create_logger(TEST_LOGGER_NAME, LogLevel.INFO)
        library.write_log(TEST_LOGGER_NAME, LogLevel.INFO, TEST_LOG_MESSAGE)

    configuration_name = JAVA_TELEMETRY_NAMES.get(variable_name, variable_name)
    if test_library.lang != "java":
        configuration_name = variable_name

    configurations = test_agent.wait_for_telemetry_configurations()
    entries = configurations.get(configuration_name)
    assert entries, f"No telemetry configuration '{configuration_name}'"
    assert int(entries[0]["value"]) == expected_value
