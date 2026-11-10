"""Reject invalid backend report encodings instead of repairing them in product tests."""

from unittest.mock import patch

from utils import features, interfaces, pytest, scenario_groups, scenarios
from utils.dd_types import DataDogAgentTrace, DataDogAgentSpan
from utils._context.weblog_metadata import WeblogMetaData
from utils._context._scenarios.security_smoke import SecuritySmoke
from utils._weblog import HttpResponse
from tests.appsec.smoke_tests.utils import assert_backend_blocked, get_backend_report


@features.not_reported
@scenarios.test_the_test
class Test_SecuritySmokeReports:
    @pytest.mark.parametrize("trace_format", ["legacy", "legacy_metadata", "efficient"])
    def test_reject_string_report(self, trace_format: str) -> None:
        span = self._span(trace_format, "gaVydWxlc5A=")
        with pytest.raises(AssertionError, match="structured appsec report"):
            get_backend_report(span, "appsec", "_dd.appsec.json")

    @pytest.mark.parametrize("trace_format", ["legacy", "efficient"])
    def test_decode_structured_report(self, trace_format: str) -> None:
        report = {"triggers": [{"rule": {"id": "test-rule"}}]}
        assert get_backend_report(self._span(trace_format, report), "appsec") == report

    @pytest.mark.parametrize(
        ("trace_format", "location"),
        [
            ("legacy", "meta"),
            ("legacy", "payload"),
            ("efficient", "meta"),
            ("efficient", "payload"),
            ("efficient", "tracer_payload"),
        ],
    )
    def test_environment_encoding(self, trace_format: str, location: str) -> None:
        span = self._span(trace_format, None)
        content: dict[str, object] = {"env": "agent-env"}
        if location == "meta":
            span.meta["env"] = "system-tests"
        elif location == "payload":
            content["env"] = "system-tests"
        elif location == "tracer_payload":
            content["idxTracerPayloads"] = [
                {"envRef": "unrelated-env", "chunks": [{}]},
                {"envRef": "system-tests", "chunks": [span.trace.raw_trace]},
            ]
        span.trace.data["request"] = {"content": content}
        assert span.get_span_env() == "system-tests"

    @pytest.mark.parametrize("location", ["meta", "tracer_payload", "agent"])
    def test_environment_precedence(self, location: str) -> None:
        span = self._span("efficient", None)
        span.raw_span["envRef"] = "unused-span-env"
        content: dict[str, object] = {"env": "agent-env"}
        if location != "agent":
            content["idxTracerPayloads"] = [{"envRef": "tracer-env", "chunks": [span.trace.raw_trace]}]
        if location == "meta":
            span.meta["env"] = "meta-env"
        span.trace.data["request"] = {"content": content}
        assert (
            span.get_span_env() == {"meta": "meta-env", "tracer_payload": "tracer-env", "agent": "agent-env"}[location]
        )

    def test_span_environment_ref_alone_is_not_backend_environment(self) -> None:
        span = self._span("efficient", None)
        span.raw_span["envRef"] = "unused-span-env"
        assert span.get_span_env() == ""

    @pytest.mark.parametrize(
        ("trace_format", "status", "location", "valid"),
        [
            ("legacy", "403", "meta", True),
            ("efficient", "403", "meta", True),
            ("efficient", 403, "meta", True),
            ("efficient", 403.0, "meta", True),
            ("legacy", 403, "meta", False),
            ("legacy", 403, "metrics", True),
            ("legacy", 403.0, "metrics", True),
            ("legacy", 403.5, "metrics", False),
            ("legacy", True, "metrics", False),
        ],
    )
    def test_blocking_status_encoding(
        self, trace_format: str, status: str | float, location: str, *, valid: bool
    ) -> None:
        span = self._span(trace_format, None)
        span.meta["appsec.blocked"] = "true"
        if location == "metrics":
            span.raw_span["metrics"] = {"http.status_code": status}
        else:
            span.meta["http.status_code"] = status
        response = HttpResponse(
            {
                "request": {"method": "GET", "url": "http://weblog/waf", "params": {}},
                "status_code": 403,
                "text": "",
                "cookies": {},
            }
        )
        with patch.object(interfaces.mocked_backend, "get_spans", return_value=[({}, span)]):
            if valid:
                assert_backend_blocked(response)
            else:
                with pytest.raises(AssertionError, match="blocking flag and HTTP status"):
                    assert_backend_blocked(response)

    @staticmethod
    def _span(trace_format: str, report: object) -> DataDogAgentSpan:
        if trace_format == "legacy":
            raw = {"meta": {}, "metaStruct": {"appsec": report}}
        elif trace_format == "legacy_metadata":
            raw = {"meta": {"appsec": report}}
        else:
            raw = {"attributes": {"appsec": report}}
        builder = (
            DataDogAgentTrace.from_agent_v1 if trace_format == "efficient" else DataDogAgentTrace.from_agent_legacy
        )
        return builder({}, {"spans": [raw]}).spans[0]


@features.not_reported
@scenarios.test_the_test
class Test_SecuritySmokeMatrix:
    @pytest.mark.parametrize(
        ("library", "weblog"),
        [
            ("python", "flask-poc"),
            ("java", "spring-boot"),
            ("nodejs", "express5"),
            ("golang", "net-http-orchestrion"),
            ("dotnet", "poc"),
            ("ruby", "rails80"),
            ("php", "apache-mod-8.2"),
        ],
    )
    def test_one_weblog_per_topology(self, library: str, weblog: str) -> None:
        for scenario in (
            *scenario_groups.security_smoke.scenarios,
            *scenario_groups.security_smoke_runtime_activation.scenarios,
        ):
            selected = [
                metadata.name
                for metadata in WeblogMetaData.load(library)
                if metadata.support_scenario(scenario.name, scenario.weblog_categories)
            ]
            assert selected == [weblog]

    def test_complete_matrix(self) -> None:
        for group in (scenario_groups.security_smoke, scenario_groups.security_smoke_runtime_activation):
            assert len(group.scenarios) == 8
            configurations = set()
            for scenario in group.scenarios:
                assert isinstance(scenario, SecuritySmoke)
                configurations.add((scenario.otel_api, scenario.otlp, scenario.otel_semantics))
            assert configurations == {
                (api, otlp, semantics) for api in (False, True) for otlp in (False, True) for semantics in (False, True)
            }
