"""Test startup log behavior for tracer libraries across supported languages."""

import contextlib
import re
import time

import pytest

from utils import scenarios, features, context, logger
from .conftest import APMLibrary

parametrize = pytest.mark.parametrize

# Regex pattern for matching startup log entries across all tracer libraries
STARTUP_LOG_PATTERN = r"DATADOG (TRACER )?CONFIGURATION( - (CORE|TRACING|PROFILING|.*))?"

# Defense-in-depth caps for the container stderr read in _get_startup_logs: whichever limit is
# hit first stops the read, so an unbounded stream can't hang the suite. All are far above any
# real tracer's startup output, so they never truncate logs in normal operation.
_STARTUP_LOG_MAX_LINES = 50_000
_STARTUP_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
_STARTUP_LOG_MAX_SECONDS = 30.0

# Boolean fields every tracer publishes in its startup diagnostic configuration describing
# whether traces/metrics/logs are exported over OTLP.
OTLP_EXPORT_FIELDS = (
    "otlp_traces_export_enabled",
    "otlp_metrics_export_enabled",
    "otlp_logs_export_enabled",
)


def _extract_otlp_export_fields(logs: str) -> dict[str, bool]:
    """Extract the three OTLP-export booleans from the tracer startup configuration line.

    The startup diagnostic is NOT serialized uniformly across tracers:
      - JSON, " - " marker separator: Node.js ("DATADOG TRACER CONFIGURATION - {json}"),
        .NET ("DATADOG TRACER CONFIGURATION - {json}"), Ruby ("DATADOG CONFIGURATION - CORE - {json}").
      - JSON, no " - " separator: Go ("DATADOG TRACER CONFIGURATION {json}"),
        Java (SLF4J "DATADOG TRACER CONFIGURATION {json}").
      - Python dict repr, NOT JSON: "- DATADOG TRACER CONFIGURATION - {dict}" produced by
        "%s" % dict, so single-quoted keys and True/False/None -- json.loads would fail on it.

    Rather than depend on a single per-language marker or full-object decoding (Python's payload
    is not valid JSON, and the JSON payloads embed nested objects that make a naive brace match
    fragile), the config line is located by field name and each boolean is read directly with a
    quote-style- and casing-tolerant regex. An UNQUOTED true/false/True/False is required, so a
    string-encoded value such as "true" would not match -- this preserves the guarantee that each
    field is emitted as a real boolean.
    """
    config_line = None
    for line in logs.splitlines():
        if OTLP_EXPORT_FIELDS[0] in line:
            config_line = line
            break
    assert config_line is not None, (
        f"No tracer startup configuration line containing '{OTLP_EXPORT_FIELDS[0]}' found. "
        f"Logs (first 2000 chars): {logs[:2000]}"
    )

    fields: dict[str, bool] = {}
    for name in OTLP_EXPORT_FIELDS:
        match = re.search(rf"""["']?{name}["']?\s*:\s*(true|false|True|False)\b""", config_line)
        assert match, (
            f"Field '{name}' not present as a boolean in the startup configuration line. Config line: {config_line}"
        )
        fields[name] = match.group(1).lower() == "true"
    return fields


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
    - Other libraries: Reads from stderr

    Args:
        test_library: The APMLibrary test client
        required: If True, fails test when logs not found. If False, returns None.

    Returns:
        Log content as string, or None if not found and not required.

    """
    if context.library == "dotnet":
        return _get_dotnet_startup_logs(test_library, required=required)

    # Bound the stderr read so a misbehaving tracer emitting an unbounded stream (e.g. a logging
    # feedback loop) can't hang the suite -- a one-shot container.logs() read would chase that
    # moving target forever. Stream the current snapshot (follow=False self-terminates at its end)
    # and stop at the first of the line/byte/time caps.
    #
    # Read the whole bounded snapshot rather than stopping at the first startup-config marker:
    # some tracers emit asserted-on content after it (Ruby logs "CONFIGURATION - CORE" at init,
    # then "CONFIGURATION - TRACING" and its "Agent Error" line only after a flush). Startup logs
    # are early, so the caps never truncate them in normal runs.
    log_stream = None
    truncated = False
    buffer = bytearray()
    line_count = 0
    try:
        # stream=True yields raw byte chunks (docker log frames), not lines; a line may span
        # chunks, so we accumulate bytes and decode once at the end.
        log_stream = test_library.container.logs(stream=True, stdout=False, stderr=True, follow=False)

        deadline = time.monotonic() + _STARTUP_LOG_MAX_SECONDS
        for chunk in log_stream:
            if not chunk:
                continue
            buffer += chunk
            line_count += chunk.count(b"\n")
            if (
                line_count >= _STARTUP_LOG_MAX_LINES
                or len(buffer) >= _STARTUP_LOG_MAX_BYTES
                or time.monotonic() >= deadline
            ):
                truncated = True
                break
    except Exception as e:
        if required:
            pytest.fail(f"Failed to retrieve container logs: {e}")
        return None
    finally:
        # Release the streaming socket promptly; we may have stopped mid-snapshot at a cap.
        if log_stream is not None:
            with contextlib.suppress(Exception):
                log_stream.close()

    if truncated:
        # Never truncate silently: a cap only trips if a tracer is emitting an abnormally large
        # (likely runaway) stderr stream, which is worth surfacing in CI output.
        logger.warning(
            f"Startup-log read hit a safety cap and was truncated at {line_count} lines / "
            f"{len(buffer)} bytes; a tracer may be emitting an unbounded stderr stream."
        )

    # errors="replace" guards against a multi-byte character truncated at a cap boundary.
    return buffer.decode("utf-8", errors="replace")


@scenarios.parametric
@features.log_tracer_status_at_startup
class Test_Startup_Logs:
    """Test tracer startup log behavior across all supported languages."""

    def test_startup_logs_default(self, test_library: APMLibrary):
        """Verify default startup log behavior when DD_TRACE_STARTUP_LOGS is not set."""
        with test_library:
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
            logs = _get_startup_logs(test_library, required=True)

            assert logs is not None
            match = re.search(STARTUP_LOG_PATTERN, logs, re.IGNORECASE)
            assert match, (
                f"Startup log not found. Searched for pattern: '{STARTUP_LOG_PATTERN}'. "
                f"Content (first 2000 chars): {logs[:2000]}"
            )

    @parametrize(
        "library_env",
        [{"DD_TRACE_STARTUP_LOGS": "true"}],
    )
    def test_startup_logs_otlp_export_fields(self, test_library: APMLibrary):
        """Verify the OTLP-export booleans are present, are booleans, and default to false.

        No OTLP-related environment variables are set, so every implementing tracer must report
        all three fields as False. DD_TRACE_STARTUP_LOGS=true only guarantees the diagnostic is
        emitted; it does not affect the OTLP-export values. Uniform across implementing languages.
        """
        with test_library:
            logs = _get_startup_logs(test_library, required=True)

            assert logs is not None
            fields = _extract_otlp_export_fields(logs)
            for name in OTLP_EXPORT_FIELDS:
                assert fields[name] is False, (
                    f"Expected {name} to default to False (no OTLP env vars set), got {fields[name]!r}"
                )

    @parametrize(
        "library_env",
        [{"DD_TRACE_STARTUP_LOGS": "true", "OTEL_TRACES_EXPORTER": "otlp"}],
    )
    def test_startup_logs_otlp_traces_export_enabled(self, test_library: APMLibrary):
        """Verify otlp_traces_export_enabled is true when OTEL_TRACES_EXPORTER=otlp.

        Gated (via manifests) to the tracers that support OTLP trace export. Ruby and PHP do not
        support it, so they are marked irrelevant/incomplete rather than skipped in the body.
        """
        with test_library:
            logs = _get_startup_logs(test_library, required=True)

            assert logs is not None
            fields = _extract_otlp_export_fields(logs)
            assert fields["otlp_traces_export_enabled"] is True, (
                f"Expected otlp_traces_export_enabled to be True with OTEL_TRACES_EXPORTER=otlp, "
                f"got {fields['otlp_traces_export_enabled']!r}"
            )

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_STARTUP_LOGS": "true",
                "DD_METRICS_OTEL_ENABLED": "true",
                "DD_RUNTIME_METRICS_ENABLED": "true",  # .NET only flips OTLP metrics when runtime metrics are on
            }
        ],
    )
    def test_startup_logs_otlp_metrics_export_enabled(self, test_library: APMLibrary):
        """Verify otlp_metrics_export_enabled is true when DD_METRICS_OTEL_ENABLED=true."""
        with test_library:
            logs = _get_startup_logs(test_library, required=True)

            assert logs is not None
            fields = _extract_otlp_export_fields(logs)
            assert fields["otlp_metrics_export_enabled"] is True, (
                f"Expected otlp_metrics_export_enabled to be True with DD_METRICS_OTEL_ENABLED=true, "
                f"got {fields['otlp_metrics_export_enabled']!r}"
            )

    @parametrize(
        "library_env",
        [{"DD_TRACE_STARTUP_LOGS": "true", "DD_LOGS_OTEL_ENABLED": "true"}],
    )
    def test_startup_logs_otlp_logs_export_enabled(self, test_library: APMLibrary):
        """Verify otlp_logs_export_enabled is true when DD_LOGS_OTEL_ENABLED=true."""
        with test_library:
            logs = _get_startup_logs(test_library, required=True)

            assert logs is not None
            fields = _extract_otlp_export_fields(logs)
            assert fields["otlp_logs_export_enabled"] is True, (
                f"Expected otlp_logs_export_enabled to be True with DD_LOGS_OTEL_ENABLED=true, "
                f"got {fields['otlp_logs_export_enabled']!r}"
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
