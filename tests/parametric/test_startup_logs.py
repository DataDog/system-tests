"""Test startup log behavior for tracer libraries across supported languages."""

import re

import pytest

from utils import incomplete_test_app, scenarios, features, context, logger
from .conftest import APMLibrary

parametrize = pytest.mark.parametrize


@scenarios.parametric
@features.log_tracer_status_at_startup
class Test_Startup_Logs:
    """Test tracer startup log behavior across all supported languages."""

    @parametrize(
        "library_env",
        [{"DD_TRACE_STARTUP_LOGS": "true"}],
    )
    @incomplete_test_app(context.library in ("php", "cpp", "rust"), reason="Need to figure out how to test this")
    def test_startup_logs_enabled(self, test_library: APMLibrary):
        """Verify startup logs are emitted when DD_TRACE_STARTUP_LOGS=true."""
        with test_library:
            # For Node.js, startup logs are emitted when the tracer tries to send its first trace
            if context.library == "nodejs":
                with test_library.dd_start_span("test_operation", service="test_service"):
                    pass
                test_library.dd_flush()

            # For .NET, startup logs are written to a file instead of stdout/stderr
            if context.library == "dotnet":
                # Find any file starting with dotnet-tracer-managed
                success, log_files = test_library.container_exec_run(
                    "sh -c 'find / -name \"dotnet-tracer-managed*\" -type f 2>/dev/null | head -1'"
                )
                if not success or not log_files or not log_files.strip():
                    pytest.fail("Failed to find .NET startup log file: no file matching 'dotnet-tracer-managed*' found")
                log_file = log_files.strip()
                success, logs = test_library.container_exec_run(f"sh -c 'cat {log_file} 2>/dev/null || true'")
                if not success or not logs:
                    pytest.fail(f"Failed to read .NET startup log file: {log_file}")
            else:
                try:
                    logs = test_library.container.logs(stdout=True, stderr=True).decode("utf-8")
                except Exception as e:
                    pytest.fail(f"Failed to retrieve container logs: {e}")

            startup_log_pattern = r"DATADOG (TRACER )?CONFIGURATION( - (CORE|TRACING|PROFILING|.*))?"
            match = re.search(startup_log_pattern, logs, re.IGNORECASE)
            assert match, (
                f"Startup log not found. Searched for pattern: '{startup_log_pattern}'. "
                f"Content (first 2000 chars): {logs[:2000]}"
            )

    @parametrize(
        "library_env",
        [{"DD_TRACE_STARTUP_LOGS": "false"}],
    )
    @incomplete_test_app(
        context.library in ("php", "cpp", "rust", "java", "python"), reason="Need to figure out how to test this"
    )
    def test_startup_logs_disabled(self, test_library: APMLibrary):
        """Verify startup logs are suppressed when DD_TRACE_STARTUP_LOGS=false."""
        with test_library:
            # For Node.js, trigger a trace to ensure startup logs would be emitted if enabled
            if context.library == "nodejs":
                with test_library.dd_start_span("test_operation", service="test_service"):
                    pass
                test_library.dd_flush()

            # For .NET, startup logs are written to a file instead of stdout/stderr
            if context.library == "dotnet":
                # Find any file starting with dotnet-tracer-managed
                success, log_files = test_library.container_exec_run(
                    "sh -c 'find / -name \"dotnet-tracer-managed*\" -type f 2>/dev/null | head -1'"
                )
                # File may not exist or be empty when startup logs are disabled
                if success and log_files and log_files.strip():
                    log_file = log_files.strip()
                    success, logs = test_library.container_exec_run(f"sh -c 'cat {log_file} 2>/dev/null || true'")
                    if success and logs:
                        startup_log_pattern = r"DATADOG (TRACER )?CONFIGURATION( - (CORE|TRACING|PROFILING|.*))?"
                        if re.search(startup_log_pattern, logs, re.IGNORECASE):
                            pytest.fail(
                                f"Startup log found in .NET log file when DD_TRACE_STARTUP_LOGS=false. "
                                f"File: {log_file}. Content (first 1000 chars): {logs[:1000]}"
                            )
                # If file doesn't exist or is empty, that's expected when startup logs are disabled
            else:
                try:
                    logs = test_library.container.logs(stdout=True, stderr=True).decode("utf-8")
                except Exception as e:
                    pytest.fail(f"Failed to retrieve container logs: {e}")

                startup_log_pattern = r"DATADOG (TRACER )?CONFIGURATION( - (CORE|TRACING|PROFILING|.*))?"
                match = re.search(startup_log_pattern, logs, re.IGNORECASE)
                if match:
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
    @incomplete_test_app(
        context.library in ("php", "cpp", "rust", "dotnet"), reason="Need to figure out how to test this"
    )
    def test_startup_logs_diagnostic_agent_unreachable(self, test_library: APMLibrary):
        """Verify diagnostic messages appear when agent is unreachable."""
        with test_library:
            with test_library.dd_start_span("test_operation", service="test_service") as span:
                span.set_meta("test_key", "test_value")
            test_library.dd_flush()

            try:
                logs = test_library.container.logs(stdout=True, stderr=True).decode("utf-8")
            except Exception as e:
                pytest.fail(f"Failed to retrieve container logs: {e}")

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
