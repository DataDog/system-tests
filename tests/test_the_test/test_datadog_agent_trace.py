"""Backend span metadata across legacy and efficient Agent trace payloads."""

from utils import features, pytest, scenarios
from utils.dd_types import DataDogAgentSpan, DataDogAgentTrace


def _span(trace_format: str) -> DataDogAgentSpan:
    if trace_format == "legacy":
        return DataDogAgentTrace.from_agent_legacy({}, {"spans": [{"meta": {}}]}).spans[0]
    return DataDogAgentTrace.from_agent_v1({}, {"spans": [{"attributes": {}}]}).spans[0]


@features.not_reported
@scenarios.test_the_test
class Test_AgentSpanEnvironment:
    @pytest.mark.parametrize(
        ("trace_format", "location"),
        [
            ("legacy", "meta"),
            ("legacy", "payload"),
            ("legacy", "tracer_payload"),
            ("efficient", "meta"),
            ("efficient", "payload"),
            ("efficient", "tracer_payload"),
            ("efficient", "indexed_tracer_payload"),
        ],
    )
    def test_environment_encoding(self, trace_format: str, location: str) -> None:
        span = _span(trace_format)
        content: dict[str, object] = {"env": "agent-env"}
        if location == "meta":
            span.meta["env"] = "system-tests"
        elif location == "payload":
            content["env"] = "system-tests"
        elif location == "indexed_tracer_payload":
            content["idxTracerPayloads"] = [
                {"strings": ["", "system-tests"], "envRef": 1, "chunks": [span.trace.raw_trace]}
            ]
        elif location == "tracer_payload":
            key = "env" if trace_format == "legacy" else "envRef"
            content["tracerPayloads" if trace_format == "legacy" else "idxTracerPayloads"] = [
                {key: "unrelated-env", "chunks": [{}]},
                {key: "system-tests", "chunks": [span.trace.raw_trace]},
            ]
        span.trace.data["request"] = {"content": content}
        assert span.get_span_env() == "system-tests"

    @pytest.mark.parametrize("location", ["meta", "tracer_payload", "agent"])
    @pytest.mark.parametrize("trace_format", ["legacy", "efficient"])
    def test_environment_precedence(self, trace_format: str, location: str) -> None:
        span = _span(trace_format)
        span.raw_span["envRef"] = "unused-span-env"
        content: dict[str, object] = {"env": "agent-env"}
        if location != "agent":
            key = "env" if trace_format == "legacy" else "envRef"
            content["tracerPayloads" if trace_format == "legacy" else "idxTracerPayloads"] = [
                {key: "tracer-env", "chunks": [span.trace.raw_trace]}
            ]
        if location == "meta":
            span.meta["env"] = "meta-env"
        span.trace.data["request"] = {"content": content}
        assert (
            span.get_span_env() == {"meta": "meta-env", "tracer_payload": "tracer-env", "agent": "agent-env"}[location]
        )

    @pytest.mark.parametrize("environment_ref", [-1, 1, None, ""])
    def test_unresolved_environment_uses_agent_environment(self, environment_ref: int | str | None) -> None:
        span = _span("efficient")
        span.trace.data["request"] = {
            "content": {
                "env": "agent-env",
                "idxTracerPayloads": [{"strings": [""], "envRef": environment_ref, "chunks": [span.trace.raw_trace]}],
            }
        }
        assert span.get_span_env() == "agent-env"

    def test_span_environment_ref_alone_is_not_backend_environment(self) -> None:
        span = _span("efficient")
        span.raw_span["envRef"] = "unused-span-env"
        assert span.get_span_env() == ""


@features.not_reported
@scenarios.test_the_test
class Test_AgentSpanTags:
    @pytest.mark.parametrize(
        ("trace_format", "value", "location", "expected"),
        [
            ("legacy", "403", "meta", "403"),
            ("efficient", "403", "meta", "403"),
            ("efficient", 403, "meta", "403"),
            ("efficient", 403.0, "meta", "403"),
            ("legacy", 403, "meta", 403),
            ("legacy", 403, "metrics", "403"),
            ("legacy", 403.0, "metrics", "403"),
            ("legacy", 403.5, "metrics", 403.5),
            ("legacy", True, "metrics", True),
            ("efficient", True, "meta", True),
        ],
    )
    def test_status_encoding(self, trace_format: str, value: str | float, location: str, expected: str | float) -> None:
        span = _span(trace_format)
        if location == "metrics":
            span.raw_span["metrics"] = {"http.status_code": value}
        else:
            span.meta["http.status_code"] = value
        actual = span.get_tag("http.status_code")
        assert actual == expected
        assert type(actual) is type(expected)

    def test_metadata_takes_precedence_over_metrics(self) -> None:
        span = _span("legacy")
        span.meta["http.status_code"] = "200"
        span.raw_span["metrics"] = {"http.status_code": 403}
        assert span.get_tag("http.status_code") == "200"

    @pytest.mark.parametrize("trace_format", ["legacy", "efficient"])
    def test_missing_tag(self, trace_format: str) -> None:
        span = _span(trace_format)
        assert span.get_tag("http.status_code") is None
        assert span.get_tag("http.status_code", "missing") == "missing"
