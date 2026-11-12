"""Backend span metadata across legacy and efficient Agent trace payloads."""

from utils import features, pytest, scenarios
from utils.dd_types import DataDogAgentTrace


@features.not_reported
@scenarios.test_the_test
class Test_AgentSpanMetadata:
    @pytest.mark.parametrize(
        ("metadata", "tracer_environment", "expected"),
        [
            ({"env": "span-env"}, "tracer-env", "span-env"),
            ({}, "tracer-env", "tracer-env"),
            ({}, "", "agent-env"),
        ],
    )
    def test_environment_precedence(self, metadata: dict[str, str], tracer_environment: str, expected: str) -> None:
        chunk = {"spans": [{"meta": metadata}]}
        content = {
            "env": "agent-env",
            "tracerPayloads": [
                {"env": "unrelated-env", "chunks": [{}]},
                {"env": tracer_environment, "chunks": [chunk]},
            ],
        }
        span = DataDogAgentTrace.from_agent_legacy({"request": {"content": content}}, chunk).spans[0]
        assert span.get_span_env() == expected

    @pytest.mark.parametrize("environment", [1, "tracer-env"])
    def test_efficient_environment(self, environment: int | str) -> None:
        chunk = {"spans": [{"attributes": {}, "envRef": "unused-span-env"}]}
        content = {
            "env": "agent-env",
            "idxTracerPayloads": [
                {"envRef": "unrelated-env", "chunks": [{}]},
                {"strings": ["", "tracer-env"], "envRef": environment, "chunks": [chunk]},
            ],
        }
        span = DataDogAgentTrace.from_agent_v1({"request": {"content": content}}, chunk).spans[0]
        assert span.get_span_env() == "tracer-env"

    @pytest.mark.parametrize("status", [403, 403.0])
    def test_numeric_status(self, status: float) -> None:
        span = DataDogAgentTrace.from_agent_legacy(
            {}, {"spans": [{"meta": {}, "metrics": {"http.status_code": status}}]}
        ).spans[0]
        assert span.get_tag("http.status_code") == "403"

    def test_legacy_metadata_takes_precedence(self) -> None:
        span = DataDogAgentTrace.from_agent_legacy(
            {}, {"spans": [{"meta": {"http.status_code": 200}, "metrics": {"http.status_code": 403}}]}
        ).spans[0]
        assert span.get_tag("http.status_code") == 200
