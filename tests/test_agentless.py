"""Direct-to-intake delivery (DD_AGENTLESS_ENABLED), without a Datadog Agent.

Endpoints and payload shapes below were confirmed against a live weblog build of the
(unmerged) `bob/agentless-setting` branch of dd-trace-py: trace submission is plain JSON
(not the msgpack v0.4 format `interfaces.agent.get_spans_list()` parses), keyed by
`traces[].spans[]`, each span using the same field names as the agent-relayed format;
stats submission reuses the msgpack `ClientStatsPayload` shape byte-for-byte. Re-confirm
against real proxy captures if the branch's wire format changes before it merges; see
utils/_context/_scenarios/agentless_endtoend.py and debugger_agentless.py for the scenario setup.
"""

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


@scenarios.apm_tracing_agentless
@features.not_reported
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
                "datadog-meta-lang": "python",
                "datadog-meta-lang-interpreter": "CPython",
                "datadog-client-computed-top-level": "true",
            },
            present=(
                "user-agent",
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
            f"Trace submission body doesn't look compressed: {wire_length} wire bytes vs "
            f"{decoded_length} decoded bytes"
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
                "datadog-meta-lang": "python",
                "datadog-meta-lang-interpreter": "CPython",
            },
            present=(
                "user-agent",
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
        for prev, cur in zip(sequences, sequences[1:]):
            assert cur == prev + 1, f"Sequence should increment by exactly 1 per flush, got: {sequences}"


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
