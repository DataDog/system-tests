"""Reject invalid backend report encodings instead of repairing them in product tests."""

from utils import features, pytest, scenarios
from utils.dd_types import DataDogAgentTrace, DataDogAgentSpan
from utils._context.weblog_metadata import WeblogMetaData
from tests.appsec.smoke_tests.utils import get_backend_report


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
        for scenario in (scenarios.security_smoke, scenarios.security_smoke_otel_api, scenarios.security_smoke_ddot):
            selected = [
                metadata.name
                for metadata in WeblogMetaData.load(library)
                if metadata.support_scenario(scenario.name, scenario.weblog_categories)
            ]
            expected = [] if scenario == scenarios.security_smoke_ddot and library in ("ruby", "php") else [weblog]
            assert selected == expected
