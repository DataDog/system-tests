"""Validate backend report carriers and Remote Config acknowledgement matching."""

from unittest.mock import patch
from collections.abc import Callable
from typing import Any

from utils import features, interfaces, pytest, remote_config as rc, scenarios
from utils.dd_types import DataDogAgentTrace, DataDogAgentSpan
from tests.appsec.smoke_tests.utils import get_backend_report, wait_for_config_acknowledged


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
            ("efficient", "indexed_tracer_payload"),
        ],
    )
    def test_environment_encoding(self, trace_format: str, location: str) -> None:
        span = self._span(trace_format, None)
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
class Test_SecuritySmokeRemoteConfig:
    @pytest.mark.parametrize("include_ack", [False, True])
    def test_rules_wait_for_matching_ack(self, *, include_ack: bool) -> None:
        state = rc.RemoteConfigStateResults(
            version=17, configs={"rules": {"product": "ASM_DD", "apply_state": rc.ApplyState.UNACKNOWLEDGED}}
        )

        def poll(version: int, config_id: str, product: str, apply_state: rc.ApplyState) -> dict[str, Any]:
            return {
                "path": "/v0.7/config",
                "request": {
                    "content": {
                        "client": {
                            "state": {
                                "targets_version": version,
                                "config_states": [{"id": config_id, "product": product, "apply_state": apply_state}],
                            }
                        }
                    }
                },
            }

        polls = [
            poll(16, "rules", "ASM_DD", rc.ApplyState.ACKNOWLEDGED),
            poll(17, "other", "ASM_DD", rc.ApplyState.ACKNOWLEDGED),
            poll(17, "rules", "ASM_DATA", rc.ApplyState.ACKNOWLEDGED),
            poll(17, "rules", "ASM_DD", rc.ApplyState.UNKNOWN),
            poll(17, "rules", "ASM_DD", rc.ApplyState.UNACKNOWLEDGED),
            poll(17, "rules", "ASM_DD", rc.ApplyState.ERROR),
        ]
        if include_ack:
            polls.append(poll(17, "rules", "ASM_DD", rc.ApplyState.ACKNOWLEDGED))

        def wait_for(predicate: Callable[[dict[str, Any]], bool], *, timeout: int) -> bool:
            assert timeout > 0
            outcomes = [predicate(data) for data in polls]
            assert outcomes == [False] * 6 + ([True] if include_ack else [])
            return any(outcomes)

        with patch.object(interfaces.library, "wait_for", side_effect=wait_for):
            assert wait_for_config_acknowledged(state, "rules") == include_ack
