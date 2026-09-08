"""Direct-to-intake delivery (DD_AGENTLESS_ENABLED), without a Datadog Agent.

Endpoints and payload shapes below were confirmed against a live weblog build of the
(unmerged) `bob/agentless-setting` branch of dd-trace-py: trace submission is plain JSON
(not the msgpack v0.4 format `interfaces.agent.get_spans_list()` parses), keyed by
`traces[].spans[]`, each span using the same field names as the agent-relayed format;
stats submission reuses the msgpack `ClientStatsPayload` shape byte-for-byte. Re-confirm
against real proxy captures if the branch's wire format changes before it merges; see
utils/_context/_scenarios/agentless_endtoend.py and debugger_agentless.py for the scenario setup.
"""

import itertools
import json
import time

from utils import features, interfaces, scenarios, weblog
from utils._context._scenarios.agentless_endtoend import AGENTLESS_MOCK_API_KEY
from utils._remote_config import send_apm_tracing_command
from utils.dd_constants import RemoteConfigApplyState as ApplyState

TRACE_SUBMISSION_PATH = "/v1/input"
TRACE_SUBMISSION_HOST = "browser-intake-mock-intake.invalid"

STATS_PATH = "/api/v0.2/stats"
STATS_HOST = "trace.agent.mock-intake.invalid"

RC_CONFIGURATIONS_PATH = "/api/v0.1/configurations"
RC_HOST = "config.mock-intake.invalid"

TELEMETRY_PATH = "/api/v2/apmtelemetry"
TELEMETRY_HOST = "instrumentation-telemetry-intake.mock-intake.invalid"

# Only the full crash report itself rides the telemetry intake (as a "logs" event, see
# Test_Agentless_Crashtracking below); the separate errors-intake upload goes to its own
# dedicated host, independently derived (not from whatever endpoint the telemetry path uses) -
# see PROD_ERRORS_INTAKE_SUBDOMAIN in libdd-crashtracker/src/crash_info/errors_intake.rs.
CRASH_ERRORS_INTAKE_HOST = "error-tracking-intake.mock-intake.invalid"
CRASH_ERRORS_INTAKE_PATH = "/api/v2/errorsintake"

# OpenTelemetry log/metric export are wholly separate agentless mechanisms (their own
# DD_SITE-derived host/flags), unrelated to the DD_AGENTLESS_ENABLED trace/stats/RC/telemetry
# paths above.
OTLP_HOST = "otlp.mock-intake.invalid"
OTLP_LOGS_PATH = "/v1/logs"
OTLP_METRICS_PATH = "/v1/metrics"

ROOT_SPAN_RESOURCE = "GET /"


def _headers(request: dict) -> dict[str, str]:
    return {name.lower(): value for name, value in request["request"]["headers"]}


def _assert_headers(headers: dict[str, str], *, exact: dict[str, str], present: tuple[str, ...]) -> None:
    """Assert exact values for deterministic headers and mere presence for value-varying ones."""
    for name, value in exact.items():
        assert headers.get(name) == value, f"header {name!r}: expected {value!r}, got {headers.get(name)!r}"
    for name in present:
        assert name in headers, f"missing required header {name!r}"


def _assert_api_key(headers: dict[str, str]) -> None:
    assert headers["dd-api-key"] in {AGENTLESS_MOCK_API_KEY, "--redacted--"}


def _requests_at(host: str, path: str) -> list[dict]:
    return [data for data in interfaces.datadog_direct.get_data(path) if data["host"] == host]


def _find_root_span(resource: str) -> dict | None:
    """Search every captured trace-submission request for a root span with this resource."""
    for request in _requests_at(TRACE_SUBMISSION_HOST, TRACE_SUBMISSION_PATH):
        for trace in request["request"]["content"].get("traces", []):
            for span in trace.get("spans", []):
                if span.get("parent_id") == "0000000000000000" and span.get("resource") == resource:
                    return span
    return None


def _find_stats_entry(resource: str) -> dict | None:
    """Search every captured stats request for a bucket entry with this resource."""
    for request in _requests_at(STATS_HOST, STATS_PATH):
        content = request["request"]["content"]
        for payload in content.get("Stats", []):
            for bucket in payload.get("Stats", []):
                for entry in bucket.get("Stats", []):
                    if entry.get("Resource") == resource:
                        return entry
    return None


def _stats_runtime_id(request: dict) -> str | None:
    payloads = request["request"]["content"].get("Stats", [])
    return payloads[0]["RuntimeID"] if payloads else None


def _stats_requests_by_runtime(runtime_id: str) -> list[dict]:
    return [r for r in _requests_at(STATS_HOST, STATS_PATH) if _stats_runtime_id(r) == runtime_id]


def _telemetry_events(request_type: str) -> list[dict]:
    """Flatten every captured telemetry request into individual events, unwrapping message-batch."""
    events = []
    for request in _requests_at(TELEMETRY_HOST, TELEMETRY_PATH):
        content = request["request"]["content"]
        if content.get("request_type") == request_type:
            events.append(content)
        elif content.get("request_type") == "message-batch":
            events.extend(p for p in content.get("payload", []) if p.get("request_type") == request_type)
    return events


def _find_metric_series(metric: str, namespace: str) -> dict | None:
    """Search every captured generate-metrics event for a series with this metric/namespace.

    The namespace lives on the payload itself (one namespace per generate-metrics event), not
    on each individual series entry - confirmed against a live proxy capture.
    """
    for event in _telemetry_events("generate-metrics"):
        payload = event["payload"]
        if payload.get("namespace") != namespace:
            continue
        for series in payload.get("series", []):
            if series.get("metric") == metric:
                return series
    return None


def _find_crash_report_log() -> dict | None:
    """Search captured telemetry "logs" events for the full crash report.

    Crashtracker sends a lightweight "ping" log as soon as config/metadata are available,
    then the full symbolicated report once collection finishes - distinguish them by tags
    (only the ping carries is_crash_ping:true), matching the convention already used by
    tests/parametric/test_crashtracking.py for the agent-mode equivalent.
    """
    for event in _telemetry_events("logs"):
        for log in event["payload"].get("logs", []):
            tags = log.get("tags", "")
            if "is_crash:true" in tags and "is_crash_ping:true" not in tags:
                return log
    return None


def _find_otlp_log_record(body_substring: str) -> dict | None:
    """Search every captured OTLP log-export request for a record whose body contains this text."""
    for request in _requests_at(OTLP_HOST, OTLP_LOGS_PATH):
        content = request["request"]["content"]
        for resource_log in content.get("resourceLogs", []):
            for scope_log in resource_log.get("scopeLogs", []):
                for record in scope_log.get("logRecords", []):
                    if body_substring in record.get("body", {}).get("stringValue", ""):
                        return record
    return None


def _find_otlp_metric_datapoint(metric_name: str) -> dict | None:
    """Search every captured OTLP metric-export request for a data point of this metric."""
    for request in _requests_at(OTLP_HOST, OTLP_METRICS_PATH):
        content = request["request"]["content"]
        for resource_metric in content.get("resourceMetrics", []):
            for scope_metric in resource_metric.get("scopeMetrics", []):
                for metric in scope_metric.get("metrics", []):
                    if metric.get("name") != metric_name:
                        continue
                    data_points = metric.get("sum", {}).get("dataPoints", [])
                    if data_points:
                        return data_points[0]
    return None


@scenarios.apm_tracing_agentless
@features.dd_agentless_enabled
class Test_Agentless_Trace_Submission:
    """Traces are sent directly to the intake, bypassing the Datadog Agent."""

    def setup_trace_submission(self):
        self.r = weblog.get("/")

    def test_trace_submission(self):
        assert self.r.status_code == 200

        requests = _requests_at(TRACE_SUBMISSION_HOST, TRACE_SUBMISSION_PATH)
        assert len(requests) != 0, f"No request captured on {TRACE_SUBMISSION_HOST}{TRACE_SUBMISSION_PATH}"

        request = requests[-1]
        assert request["response"]["status_code"] // 100 == 2

        headers = _headers(request)
        _assert_api_key(headers)
        _assert_headers(
            headers,
            exact={
                "content-type": "application/json",
                "content-encoding": "zstd",
                "datadog-client-computed-top-level": "true",
            },
            present=(
                "user-agent",
                # Language-identifying headers vary per tracer (e.g. "python"/"CPython" vs.
                # "nodejs"/"v8"); only their presence is invariant across languages.
                "datadog-meta-lang",
                "datadog-meta-lang-interpreter",
                "datadog-meta-lang-version",
                "datadog-meta-tracer-version",
                "datadog-entity-id",
                "x-datadog-trace-count",
                "content-length",
            ),
        )
        assert headers["user-agent"].startswith("Tracer/")

        # The proxy transparently decompresses the body for capture (request["request"]["length"]
        # is the decompressed size); compare it against the real over-the-wire content-length
        # header to confirm the payload was actually compressed, not just labeled as such.
        wire_length = int(headers["content-length"])
        decoded_length = request["request"]["length"]
        assert wire_length < decoded_length, (
            f"Trace submission body doesn't look compressed: {wire_length} wire bytes vs {decoded_length} decoded bytes"
        )

        content = request["request"]["content"]
        assert content, "Trace submission request body is empty"

        span = _find_root_span(ROOT_SPAN_RESOURCE)
        assert span is not None, f"No root span with resource {ROOT_SPAN_RESOURCE!r} was captured"
        assert span["service"] == "weblog"
        assert span["type"] == "web"
        assert span["error"] == 0
        assert span["meta"]["http.method"] == "GET"
        assert span["meta"]["http.status_code"] == "200"


@scenarios.apm_tracing_agentless
@features.client_side_stats_supported
class Test_Agentless_Stats:
    """Client-side trace stats are sent directly to the intake, on their own endpoint."""

    def setup_stats(self):
        self.r = weblog.get("/")

    def test_stats(self):
        assert self.r.status_code == 200

        stats_requests = _requests_at(STATS_HOST, STATS_PATH)
        assert len(stats_requests) != 0, f"No request captured on {STATS_HOST}{STATS_PATH}"

        request = stats_requests[-1]
        assert request["response"]["status_code"] // 100 == 2

        headers = _headers(request)
        _assert_api_key(headers)
        _assert_headers(
            headers,
            exact={
                "content-type": "application/msgpack",
            },
            present=(
                "user-agent",
                # Language-identifying headers vary per tracer (e.g. "python"/"CPython" vs.
                # "nodejs"/"v8"); only their presence is invariant across languages.
                "datadog-meta-lang",
                "datadog-meta-lang-interpreter",
                "datadog-meta-lang-version",
                "datadog-meta-tracer-version",
                "datadog-entity-id",
                "content-length",
            ),
        )
        assert headers["user-agent"].startswith("Tracer/")
        # Stats has no top-level-computed/trace-count headers: those are trace-submission-only.
        assert "datadog-client-computed-top-level" not in headers
        assert "x-datadog-trace-count" not in headers

        content = request["request"]["content"]
        assert content["AgentHostname"] == "weblog"
        assert content["ClientComputed"] is True

        # Stats and traces are distinct payloads on distinct hosts/paths.
        trace_requests = _requests_at(TRACE_SUBMISSION_HOST, TRACE_SUBMISSION_PATH)
        assert request not in trace_requests

        entry = _find_stats_entry(ROOT_SPAN_RESOURCE)
        assert entry is not None, f"No stats entry with resource {ROOT_SPAN_RESOURCE!r} was captured"
        assert entry["Service"] == "weblog"
        assert entry["Type"] == "web"
        assert entry["Hits"] >= 1
        assert entry["TopLevelHits"] >= 1
        assert entry["Errors"] == 0


@scenarios.apm_tracing_agentless
@features.client_side_stats_supported
class Test_Agentless_Stats_Multi_Flush:
    """Sequence increments by exactly 1 across successive flushes of the same runtime.

    Stats buckets are 10s wide; the agent-mode writer's own re-aggregation always resets
    Sequence to 0 on every relayed payload (see pkg/trace/stats/client_stats_aggregator.go),
    so this monotonic-Sequence guarantee is agentless-specific - the Agent never gave a
    real signal here to compare against, which is exactly why it's easy to get wrong.
    """

    def setup_multi_flush_stats(self):
        runtime_id = None
        deadline = time.time() + 60
        while time.time() < deadline:
            weblog.get("/")
            requests = _requests_at(STATS_HOST, STATS_PATH)
            if requests:
                runtime_id = _stats_runtime_id(requests[-1])
                if runtime_id and len(_stats_requests_by_runtime(runtime_id)) >= 2:
                    break
            time.sleep(2)
        self.runtime_id = runtime_id

    def test_multi_flush_stats(self):
        assert self.runtime_id, "No stats request was ever captured"

        requests = _stats_requests_by_runtime(self.runtime_id)
        assert len(requests) >= 2, (
            f"Expected at least 2 stats flushes for runtime {self.runtime_id!r}, got {len(requests)}"
        )

        sequences = [r["request"]["content"]["Stats"][0]["Sequence"] for r in requests]
        assert len(set(sequences)) == len(sequences), f"Sequence numbers are not unique: {sequences}"
        for prev, cur in itertools.pairwise(sequences):
            assert cur == prev + 1, f"Sequence should increment by exactly 1 per flush, got: {sequences}"


@scenarios.apm_tracing_agentless
@features.dd_agentless_enabled
class Test_Agentless_Telemetry:
    """Instrumentation telemetry - including generate-metrics, the actual transport for internal
    tracer metrics like spans_created/spans_finished - has no transport setting of its own and
    simply follows the global DD_AGENTLESS_ENABLED switch, going straight to its own dedicated
    telemetry intake host instead of through an Agent. This is distinct from (and, on this
    branch, NOT a substitute for) DogStatsD-based runtime metrics (CPU/memory/GC), which have no
    agentless transport at all and are silently dropped without an Agent - out of scope here.
    """

    def _trigger_and_wait_for_metrics(self):
        self.r = weblog.get("/")
        interfaces.datadog_direct.wait_for(
            lambda d: d["host"] == TELEMETRY_HOST
            and d["path"] == TELEMETRY_PATH
            and _find_metric_series("spans_created", "tracers") is not None,
            timeout=30,
        )

    def setup_telemetry_endpoint(self):
        self._trigger_and_wait_for_metrics()

    def test_telemetry_endpoint(self):
        assert self.r.status_code == 200

        requests = _requests_at(TELEMETRY_HOST, TELEMETRY_PATH)
        assert len(requests) != 0, f"No request captured on {TELEMETRY_HOST}{TELEMETRY_PATH}"

        request = requests[-1]
        assert request["response"]["status_code"] // 100 == 2

        content = request["request"]["content"]
        headers = _headers(request)
        _assert_api_key(headers)
        _assert_headers(
            headers,
            exact={"content-type": "application/json"},
            present=(
                "user-agent",
                "dd-telemetry-request-type",
                "dd-telemetry-api-version",
                "dd-client-library-version",
                "dd-client-library-language",
                "dd-session-id",
                "datadog-entity-id",
                "content-length",
            ),
        )
        assert headers["user-agent"].startswith("telemetry/")
        assert headers["dd-telemetry-request-type"] == content["request_type"]
        # dd-client-library-language varies per tracer; check it's self-consistent with the
        # payload's own declared language instead of hardcoding one language.
        application = content.get("application", {})
        assert headers["dd-client-library-language"] == application.get("language_name")


@scenarios.apm_tracing_agentless_fast_heartbeat
@features.dd_agentless_enabled
class Test_Agentless_Telemetry_Generate_Metrics:
    """generate-metrics events only flush on the telemetry heartbeat. The default interval
    (60s, see DD_TELEMETRY_HEARTBEAT_INTERVAL) exceeds what's practical to wait for in a single
    test, so this runs under its own scenario with a shortened heartbeat instead of forcing one
    on the whole (much larger) apm_tracing_agentless suite - mirrors telemetry_extended_heartbeat.
    """

    def setup_telemetry_generate_metrics(self):
        self.r = weblog.get("/")
        interfaces.datadog_direct.wait_for(
            lambda d: d["host"] == TELEMETRY_HOST
            and d["path"] == TELEMETRY_PATH
            and _find_metric_series("spans_created", "tracers") is not None,
            timeout=30,
        )

    def test_telemetry_generate_metrics(self):
        series = _find_metric_series("spans_created", "tracers")
        assert series is not None, "No tracers.spans_created generate-metrics event was captured"
        assert series["type"] == "count"
        assert series["common"] is True
        assert series["points"], "Metric series has no data points"
        assert series["points"][0][1] > 0


@scenarios.apm_tracing_agentless
@features.crashtracking
class Test_Agentless_Crashtracking:
    """A real crash report reaches the intake through two independent agentless mechanisms:
    a dedicated errors-intake endpoint (its own host, error-tracking-intake.<site>, derived
    independently of the telemetry path - see PROD_ERRORS_INTAKE_SUBDOMAIN in libdd-crashtracker's
    errors_intake.rs), and a "logs" telemetry event on the telemetry-intake host used by
    Test_Agentless_Telemetry. These are NOT the same host with two paths - only the full crash
    report itself rides the telemetry intake; the errors-intake upload is fully separate.

    Confirmed against a fix for a real bug on the dd-trace-py branch: crash reports were
    silently dropped agentlessly (too-short collection timeout, and the crash receiver
    subprocess's environment not forwarding HTTP(S)_PROXY, so it could never reach the mock
    intake through the proxy this test harness requires). If this test hangs/times out again,
    that regression is the first thing to check.
    """

    def _trigger_crash_and_wait(self):
        # wait_for_receiver defaults to true: the crashing child blocks in its own signal
        # handler until the receiver finishes collecting/uploading (up to the collector
        # timeout), and the parent's os.waitpid() - and thus this HTTP response - doesn't
        # return until the child actually exits. Give it real headroom past the client's
        # normal 5s default, or this legitimately times out on a slow/busy host.
        self.r = weblog.get("/spawn_child", params={"sleep": 0, "crash": "true", "fork": "true"}, timeout=45)
        # Don't gate on a single incoming event's host/path: the errors-intake request and the
        # telemetry crash-report log are two independent async events that can arrive in either
        # order, so check both conditions globally rather than on whatever `d` triggered this.
        interfaces.datadog_direct.wait_for(
            lambda _: bool(_requests_at(CRASH_ERRORS_INTAKE_HOST, CRASH_ERRORS_INTAKE_PATH))
            and _find_crash_report_log() is not None,
            timeout=90,
        )

    def setup_crash_report_errors_intake(self):
        self._trigger_crash_and_wait()

    def test_crash_report_errors_intake(self):
        assert self.r.status_code == 200

        requests = _requests_at(CRASH_ERRORS_INTAKE_HOST, CRASH_ERRORS_INTAKE_PATH)
        assert len(requests) != 0, f"No request captured on {CRASH_ERRORS_INTAKE_HOST}{CRASH_ERRORS_INTAKE_PATH}"

        request = requests[-1]
        assert request["response"]["status_code"] // 100 == 2

        headers = _headers(request)
        _assert_api_key(headers)
        _assert_headers(
            headers,
            exact={"content-type": "application/json"},
            present=("user-agent", "datadog-entity-id", "content-length"),
        )
        assert headers["user-agent"].startswith("crashtracker/")

        content = request["request"]["content"]
        assert content["ddsource"] == "crashtracker"
        assert content["error"]["is_crash"] is True
        assert content["error"]["type"] == "SIGSEGV"
        assert content["sig_info"]["si_signo_human_readable"] == "SIGSEGV"
        assert content["proc_info"]["pid"] > 0

    def setup_crash_report_telemetry_logs(self):
        self._trigger_crash_and_wait()

    def test_crash_report_telemetry_logs(self):
        log = _find_crash_report_log()
        assert log is not None, "No full crash-report telemetry logs event was captured"

        message = json.loads(log["message"])
        assert message["error"]["is_crash"] is True
        assert message["error"]["kind"] == "UnixSignal"
        assert "SIGSEGV" in message["error"]["message"]


@scenarios.apm_tracing_agentless
@features.dd_agentless_enabled
class Test_Agentless_OTLP_Logs:
    """A log record emitted via the standard OTel Logs API (`GET /otel_create_log` in the
    weblog - dd-trace-py bridges its standard `logging` module automatically, other tracers
    without such a bridge call the explicit OTel Logs API instead, mirroring how
    /otel_create_metric already handles the same language-asymmetry for metrics) is exported
    directly to the intake (https://otlp.<site>/v1/logs) when DD_LOGS_OTEL_ENABLED is set, with
    no Datadog Agent involved.
    """

    LOG_MESSAGE_MARKER = "[otel_create_log] test log record"

    def setup_otlp_log_export(self):
        self.r = weblog.get("/otel_create_log")
        interfaces.datadog_direct.wait_for(
            lambda d: d["host"] == OTLP_HOST
            and d["path"] == OTLP_LOGS_PATH
            and _find_otlp_log_record(self.LOG_MESSAGE_MARKER) is not None,
            timeout=30,
        )

    def test_otlp_log_export(self):
        requests = _requests_at(OTLP_HOST, OTLP_LOGS_PATH)
        assert len(requests) != 0, f"No request captured on {OTLP_HOST}{OTLP_LOGS_PATH}"

        request = requests[-1]
        assert request["response"]["status_code"] // 100 == 2

        headers = _headers(request)
        _assert_api_key(headers)
        _assert_headers(
            headers,
            exact={"content-type": "application/x-protobuf"},
            present=("user-agent", "content-length"),
        )

        record = _find_otlp_log_record(self.LOG_MESSAGE_MARKER)
        assert record is not None, f"No OTLP log record containing {self.LOG_MESSAGE_MARKER!r} was captured"
        assert record["severityText"] == "INFO"
        assert record["body"]["stringValue"] == self.LOG_MESSAGE_MARKER
        assert "traceId" in record
        assert "spanId" in record


@scenarios.apm_tracing_agentless
@features.dd_agentless_enabled
class Test_Agentless_OTLP_Metrics:
    """A real, user-created OTel metric (via the standard OTel Metrics API - `GET /otel_create_metric`
    calls `opentelemetry.metrics.get_meter(...).create_counter(...).add(...)` in the weblog) is
    exported directly to the intake (https://otlp.<site>/v1/metrics) when DD_METRICS_OTEL_ENABLED
    is set, with no Datadog Agent involved.
    """

    METRIC_NAME = "system_tests.otel_metric"

    def setup_otlp_metric_export(self):
        self.r = weblog.get("/otel_create_metric")
        interfaces.datadog_direct.wait_for(
            lambda d: d["host"] == OTLP_HOST
            and d["path"] == OTLP_METRICS_PATH
            and _find_otlp_metric_datapoint(self.METRIC_NAME) is not None,
            timeout=30,
        )

    def test_otlp_metric_export(self):
        assert self.r.status_code == 200

        requests = _requests_at(OTLP_HOST, OTLP_METRICS_PATH)
        assert len(requests) != 0, f"No request captured on {OTLP_HOST}{OTLP_METRICS_PATH}"

        request = requests[-1]
        assert request["response"]["status_code"] // 100 == 2

        headers = _headers(request)
        _assert_api_key(headers)
        _assert_headers(
            headers,
            exact={"content-type": "application/x-protobuf"},
            present=("user-agent", "content-length"),
        )

        data_point = _find_otlp_metric_datapoint(self.METRIC_NAME)
        assert data_point is not None, f"No OTLP data point for metric {self.METRIC_NAME!r} was captured"
        assert int(data_point.get("asInt", data_point.get("asDouble", 0))) >= 1
        attributes = {a["key"]: a["value"] for a in data_point.get("attributes", [])}
        assert attributes.get("system_tests.metric_test", {}).get("stringValue") == "true"


@scenarios.apm_tracing_agentless
@features.remote_config_object_supported
class Test_Agentless_Remote_Config:
    """The native agentless Remote Configuration client polls the intake directly.

    There is no agent to relay client state via `/v0.7/config`: the native client polls
    `/api/v0.1/configurations` directly and reports its per-config apply state inline on that
    same request (LatestConfigsRequest.active_clients[0].state) instead of via a separate
    follow-up request. send_apm_tracing_command()/send_state() (utils/_remote_config.py) now
    detect this agentless shape (keyed off `context.scenario.include_agent`), so this drives a
    real config push and confirms application the same way agent-mode RC tests do.
    """

    def setup_remote_config_poll(self):
        self.rc_state = send_apm_tracing_command(dynamic_instrumentation_enabled=True)

    def test_remote_config_poll(self):
        assert self.rc_state.state == ApplyState.ACKNOWLEDGED, (
            f"RC config was not acknowledged: state={self.rc_state.state}, configs={self.rc_state.configs}"
        )
        for config in self.rc_state.configs.values():
            assert config.get("apply_state") != ApplyState.ERROR, f"RC config apply error: {config}"

        requests = _requests_at(RC_HOST, RC_CONFIGURATIONS_PATH)
        assert len(requests) != 0, f"No request captured on {RC_HOST}{RC_CONFIGURATIONS_PATH}"

        request = requests[-1]
        assert request["method"] == "POST"

        headers = _headers(request)
        _assert_api_key(headers)
        _assert_headers(
            headers,
            exact={"content-type": "application/x-protobuf"},
            present=("user-agent", "datadog-entity-id", "content-length"),
        )
        # The native RC client is driven by libdatadog directly, not the Python-level tracer,
        # so it identifies itself distinctly (no datadog-meta-lang-* headers, unlike traces/stats).
        assert headers["user-agent"].startswith("Libdatadog/")
