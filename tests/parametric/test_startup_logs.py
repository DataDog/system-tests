"""Test startup log behavior for tracer libraries across supported languages."""

import re

from utils import pytest

from utils import scenarios, features, logger
from .conftest import APMLibrary
from .utils import get_startup_logs

parametrize = pytest.mark.parametrize

# Regex pattern for matching startup log entries across all tracer libraries
STARTUP_LOG_PATTERN = r"DATADOG (TRACER )?CONFIGURATION( - (CORE|TRACING|PROFILING|.*))?"


@scenarios.parametric
@features.log_tracer_status_at_startup
class Test_Startup_Logs:
    """Test tracer startup log behavior across all supported languages."""

    def test_startup_logs_default(self, test_library: APMLibrary):
        """Verify default startup log behavior when DD_TRACE_STARTUP_LOGS is not set."""
        with test_library:
            logs = get_startup_logs(test_library, required=True)

            assert logs is not None
            match = re.search(STARTUP_LOG_PATTERN, logs, re.IGNORECASE)
            assert match, (
                f"Startup log not found (default behavior). Searched for pattern: '{STARTUP_LOG_PATTERN}'. "
                f"Content (first 2000 chars): {logs[:2000]}"
            )

    @parametrize(
        "library_env",
        [{"DD_TRACE_STARTUP_LOGS": "true"}],
        # DD_TRACE_DEBUG and DD_TRACE_LOG_LEVEL defaults are okay here
    )
    def test_startup_logs_enabled(self, test_library: APMLibrary):
        """Verify startup logs are emitted when DD_TRACE_STARTUP_LOGS=true."""
        with test_library:
            logs = get_startup_logs(test_library, required=True)

            assert logs is not None
            match = re.search(STARTUP_LOG_PATTERN, logs, re.IGNORECASE)
            assert match, (
                f"Startup log not found. Searched for pattern: '{STARTUP_LOG_PATTERN}'. "
                f"Content (first 2000 chars): {logs[:2000]}"
            )

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_STARTUP_LOGS": "false",
                "DD_TRACE_DEBUG": "false",  # python requires DD_TRACE_DEBUG=false to suppress startup logs
                "DD_TRACE_LOG_LEVEL": "warn",  # java requires DD_TRACE_LOG_LEVEL=warn to suppress startup logs
            }
        ],
    )
    def test_startup_logs_disabled(self, test_library: APMLibrary):
        """Verify startup logs are suppressed when DD_TRACE_STARTUP_LOGS=false."""
        with test_library:
            logs = get_startup_logs(test_library, required=False)
            if logs is not None:
                match = re.search(STARTUP_LOG_PATTERN, logs, re.IGNORECASE)
                if match:
                    logger.error(logs)
                    pytest.fail(
                        f"Startup log found when DD_TRACE_STARTUP_LOGS=false. "
                        f"Found pattern: '{match.group(0)}'. "
                        f"Logs (first 1000 chars): {logs[:1000]}"
                    )

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_STARTUP_LOGS": "true",
                "DD_TRACE_AGENT_URL": "http://unreachable-host-that-does-not-exist:8126",
            }
        ],
    )
    def test_startup_logs_diagnostic_agent_unreachable(self, test_library: APMLibrary):
        """Verify diagnostic messages appear when agent is unreachable."""
        with test_library:
            # Trigger a span to force tracers to attempt connection to the agent
            # Some tracers only attempt to connect when flushing spans
            with test_library.dd_start_span("test_operation", service="test_service"):
                pass
            test_library.dd_flush()

            logs = get_startup_logs(test_library, required=True)

            assert logs is not None
            diagnostic_patterns = [
                r"Agent not reachable",
                r"Connection refused",
                r"Agent Error",
                r"Agent.*unreachable",
                r"Failed to.*agent",
                r"Could not.*connect.*agent",
                r"Connection.*failed",
                r"ECONNREFUSED",
                r"Connection.*refused",
                r"ENOTFOUND",  # DNS resolution failure (Node.js)
                r"getaddrinfo.*ENOTFOUND",  # Node.js DNS error format
            ]

            found_diagnostic = False
            matched_pattern = None
            for pattern in diagnostic_patterns:
                if re.search(pattern, logs, re.IGNORECASE):
                    found_diagnostic = True
                    matched_pattern = pattern
                    break

            assert found_diagnostic, (
                f"No diagnostic message found when agent is unreachable. "
                f"Searched for patterns: {diagnostic_patterns}. "
                f"Logs (first 2000 chars): {logs[:2000]}"
            )

            logger.info(f"Found diagnostic message with pattern: {matched_pattern}")
