"""Test startup log behavior for tracer libraries across supported languages."""

import re

import pytest

from utils import scenarios, features, context, logger
from .conftest import APMLibrary

parametrize = pytest.mark.parametrize

# Regex pattern for matching startup log entries across all tracer libraries
STARTUP_LOG_PATTERN = r"DATADOG (TRACER )?CONFIGURATION( - (CORE|TRACING|PROFILING|.*))?"


def _get_dotnet_startup_logs(test_library: APMLibrary, *, required: bool = True) -> str | None:
    """Get .NET tracer startup logs from the container (dotnet-tracer-managed* file).

    If required is True, fails the test when the file is not found or empty.
    If required is False, returns None when the file is not found or empty.
    """
    success, log_files = test_library.container_exec_run(
        "sh -c 'find / -name \"dotnet-tracer-managed*\" -type f 2>/dev/null | head -1'"
    )
    if not success or not log_files or not log_files.strip():
        if required:
            pytest.fail("Failed to find .NET startup log file: no file matching 'dotnet-tracer-managed*' found")
        return None
    log_file = log_files.strip()
    success, logs = test_library.container_exec_run(f"sh -c 'cat {log_file} 2>/dev/null || true'")
    if not success or not logs:
        if required:
            pytest.fail(f"Failed to read .NET startup log file: {log_file}")
        return None
    return logs


def _get_startup_logs(test_library: APMLibrary, *, required: bool = True) -> str | None:
    """Get startup logs from container, handling language-specific differences.

    - .NET: Reads from dotnet-tracer-managed* file
    - Node.js/Ruby: Reads from stdout
    - Other libraries: Reads from stderr

    Args:
        test_library: The APMLibrary test client
        required: If True, fails test when logs not found. If False, returns None.

    Returns:
        Log content as string, or None if not found and not required.

    """
    if context.library == "dotnet":
        return _get_dotnet_startup_logs(test_library, required=required)
    elif context.library in ("nodejs", "ruby"):
        try:
            logs = test_library.container.logs(stderr=False, stdout=True).decode("utf-8")
        except Exception as e:
            if required:
                pytest.fail(f"Failed to retrieve container logs: {e}")
            return None
    else:
        try:
            logs = test_library.container.logs(stderr=True, stdout=False).decode("utf-8")
        except Exception as e:
            if required:
                pytest.fail(f"Failed to retrieve container logs: {e}")
            return None

    return logs


@scenarios.parametric
@features.log_tracer_status_at_startup
class Test_Startup_Logs:
    """Test tracer startup log behavior across all supported languages."""

    def test_startup_logs_default(self, test_library: APMLibrary):
        """Verify default startup log behavior when DD_TRACE_STARTUP_LOGS is not set."""
        with test_library:
            # For Node.js, startup logs are emitted when the tracer tries to send its first trace
            if context.library == "nodejs":
                with test_library.dd_start_span("test_operation", service="test_service"):
                    pass
                test_library.dd_flush()

            logs = _get_startup_logs(test_library, required=True)

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
            # For Node.js, startup logs are emitted when the tracer tries to send its first trace
            if context.library == "nodejs":
                with test_library.dd_start_span("test_operation", service="test_service"):
                    pass
                test_library.dd_flush()

            logs = _get_startup_logs(test_library, required=True)

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
            # For Node.js, trigger a trace to ensure startup logs would be emitted if enabled
            if context.library == "nodejs":
                with test_library.dd_start_span("test_operation", service="test_service"):
                    pass
                test_library.dd_flush()

            logs = _get_startup_logs(test_library, required=False)
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

            logs = _get_startup_logs(test_library, required=True)

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
