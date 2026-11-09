"""Security product contracts at backend intake, shared by all three topologies."""

import json
from pathlib import Path

import jsonschema

from utils import context, features, interfaces, remote_config as rc, scenarios, weblog
from utils.dd_types import is_same_boolean
from utils.dd_types import DataDogAgentSpan
from utils._weblog import HttpResponse
from utils._context._scenarios._core import FakeDatadogKey
from utils.telemetry_utils import TelemetryUtils
from tests.appsec.smoke_tests.utils import (
    BaseRaspSmokeTests,
    BaseRemoteConfigSmokeTests,
    BaseTelemetrySmokeTests,
    BaseThreatsSmokeTests,
    BaseUserEventsSmokeTests,
    assert_backend_attack,
    get_backend_report,
)


@features.security_events_metadata
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_Threats(BaseThreatsSmokeTests):
    _rc_state = rc.backend_rc_state


@features.security_events_metadata
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_EventTags:
    def setup_event_tags(self) -> None:
        self.r = weblog.get("/waf", headers={"User-Agent": "Arachni/v1", "X-Forwarded-For": "42.42.42.42"})

    def test_event_tags(self) -> None:
        spans = [
            span
            for _, span in interfaces.mocked_backend.get_spans(self.r)
            if is_same_boolean(actual=span.meta.get("appsec.event"), expected="true")
        ]
        assert spans, "Backend did not receive a security event"
        for span in spans:
            assert span.get_span_service() == "weblog"
            assert span.meta.get("env") == "system-tests"
            assert span.metrics.get("_dd.appsec.enabled") == 1
            assert span.meta.get("http.method") == "GET"
            assert span.meta.get("http.status_code") == str(self.r.status_code)
            assert span.meta.get("http.client_ip") == "42.42.42.42"
            assert span.meta.get("network.client.ip")
            assert "Arachni/v1" in span.meta.get("http.useragent", "")
            for tag in ("_dd.appsec.waf.version", "_dd.appsec.event_rules.version", "_dd.runtime_family"):
                assert isinstance(span.meta.get(tag), str), f"Missing backend tag {tag}"
                assert span.meta[tag], f"Empty backend tag {tag}"
            for tag in ("_dd.appsec.waf.duration", "_dd.appsec.waf.duration_ext"):
                assert isinstance(span.metrics.get(tag), (int, float)), tag
                assert span.metrics[tag] >= 0, tag


@features.rasp_local_file_inclusion
@features.rasp_server_side_request_forgery
@features.rasp_sql_injection
@features.rasp_shell_injection
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_Rasp(BaseRaspSmokeTests):
    pass


@features.rasp_span_tags
@features.rasp_local_file_inclusion
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_RaspTags:
    def setup_span_tags(self) -> None:
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_span_tags(self) -> None:
        spans = [span for _, span in interfaces.mocked_backend.get_spans(self.r)]
        assert spans, "Backend did not receive the RASP request"
        assert any(is_same_boolean(actual=span.meta.get("appsec.event"), expected="true") for span in spans)
        for tag in ("_dd.appsec.rasp.duration", "_dd.appsec.rasp.duration_ext"):
            assert any(isinstance(span.metrics.get(tag), (int, float)) and span.metrics[tag] >= 0 for span in spans), (
                tag
            )
        assert any(span.metrics.get("_dd.appsec.rasp.rule.eval", 0) >= 1 for span in spans)


@features.rasp_stack_trace
@features.rasp_local_file_inclusion
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_RaspStack:
    def setup_stack_trace(self) -> None:
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_stack_trace(self) -> None:
        for _, span in interfaces.mocked_backend.get_spans(self.r):
            stacks = get_backend_report(span, "_dd.stack")
            if stacks is None:
                continue
            report = get_backend_report(span, "appsec", "_dd.appsec.json")
            assert report is not None
            stack_ids = {trigger["stack_id"] for trigger in report["triggers"] if "stack_id" in trigger}
            assert stack_ids, "RASP report must link to its exploit stack"
            exploits = stacks.get("exploit")
            assert isinstance(exploits, list), "Backend must receive exploit stack traces"
            assert exploits, "Backend must receive exploit stack traces"
            for stack in exploits:
                assert stack["id"] in stack_ids
                assert isinstance(stack.get("language"), str)
                assert stack["language"]
                assert isinstance(stack.get("frames"), list)
                assert 0 < len(stack["frames"]) <= 32
                assert any(frame.get("function") for frame in stack["frames"])
            return
        raise AssertionError("Backend did not receive a RASP exploit stack")


@features.waf_telemetry
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_Telemetry(BaseTelemetrySmokeTests):
    pass


@features.threats_configuration
@features.appsec_request_blocking
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_RemoteConfig(BaseRemoteConfigSmokeTests):
    _rc_state = rc.backend_rc_state


@features.changing_rules_using_rc
@scenarios.security_smoke_runtime_activation
@scenarios.security_smoke_otel_api_runtime_activation
@scenarios.security_smoke_ddot_runtime_activation
class Test_SecuritySmoke_RuntimeActivation:
    def setup_activation_cycle(self) -> None:
        state = rc.backend_rc_state
        self.reset_state = state.reset().apply()
        self.disabled = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})
        try:
            self.enabled_state = state.set_config(
                "datadog/2/ASM_FEATURES/asm_features_activation/config", {"asm": {"enabled": True}}
            ).apply()
            self.enabled = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})
            self.deactivated_state = state.reset().apply()
            self.deactivated = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})
        finally:
            state.reset().apply()

    def test_activation_cycle(self) -> None:
        for state in (self.reset_state, self.enabled_state, self.deactivated_state):
            assert state.state == rc.ApplyState.ACKNOWLEDGED
        config = self.enabled_state.configs["asm_features_activation"]
        assert config["apply_state"] == rc.ApplyState.ACKNOWLEDGED, config
        for response in (self.disabled, self.deactivated):
            assert response.status_code == 200
            spans = [span for _, span in interfaces.mocked_backend.get_spans(response)]
            assert spans, "Inactive AppSec must still emit the request trace"
            assert not any(is_same_boolean(actual=span.meta.get("appsec.event"), expected="true") for span in spans), (
                "Inactive AppSec must not report an attack"
            )
            assert not list(interfaces.mocked_backend.get_appsec_data(response))
        assert self.enabled.status_code == 200
        if context.scenario == scenarios.security_smoke_ddot_runtime_activation:
            assert list(interfaces.open_telemetry.get_otel_spans(self.enabled)), "Activation must use OTLP in DDOT"
            assert not list(interfaces.library.get_traces(self.enabled)), "DDOT must not fall back to native export"
        else:
            assert list(interfaces.library.get_traces(self.enabled)), "Activation must use native export"
        assert_backend_attack(self.enabled)


@features.api_security_schemas
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_ApiSecurity:
    def setup_api_security_smoke(self) -> None:
        self.r = weblog.post(
            "/tag_value/api_match_smoke/200?smoke_query=example",
            json={"smoke_body": "example"},
            cookies={"smoke_cookie": "example"},
        )

    def test_api_security_smoke(self) -> None:
        span = self._schema_span(self.r, "POST", ("req.headers", "req.query", "req.params", "req.body", "req.cookies"))
        for address, field in (
            ("req.headers", "user-agent"),
            ("req.query", "smoke_query"),
            ("req.params", "tag_value"),
            ("req.body", "smoke_body"),
            ("req.cookies", "smoke_cookie"),
        ):
            value = span.meta[f"_dd.appsec.s.{address}"][0].get(field)
            assert isinstance(value, list), f"Missing schema for {address}.{field}"
            assert value, f"Empty schema for {address}.{field}"

    def setup_response_schemas(self) -> None:
        self.r = weblog.post(
            "/tag_value/payload_in_response_body_smoke/200?X-option=smoke",
            data={"smoke_body": "example"},
        )

    def test_response_schemas(self) -> None:
        span = self._schema_span(self.r, "POST", ("res.headers", "res.body"))
        assert "x-option" in span.meta["_dd.appsec.s.res.headers"][0]
        payload = span.meta["_dd.appsec.s.res.body"][0].get("payload")
        assert isinstance(payload, list)
        assert payload
        assert "smoke_body" in payload[0]

    @staticmethod
    def _schema_span(response: HttpResponse, method: str, addresses: tuple[str, ...]) -> DataDogAgentSpan:
        assert response.status_code == 200
        for _, span in interfaces.mocked_backend.get_spans(response):
            if not all(f"_dd.appsec.s.{address}" in span.meta for address in addresses):
                continue
            assert span.meta.get("http.method") == method
            assert span.meta.get("http.status_code") == "200"
            assert span.meta.get("http.route"), "Backend schemas need the request route"
            for address in addresses:
                schema = span.meta[f"_dd.appsec.s.{address}"]
                assert isinstance(schema, list), f"Invalid backend schema for {address}"
                assert schema, f"Empty backend schema for {address}"
                assert isinstance(schema[0], dict), f"Invalid backend schema for {address}"
                assert schema[0], f"Empty backend schema for {address}"
            return span
        raise AssertionError(f"Backend did not receive all API schema tags: {addresses}")


@features.auth_schemas
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_AuthSchema:
    def setup_jwt_schema(self) -> None:
        # Well-formed JWT with a synthetic signature and a single string claim.
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzbW9rZSJ9.c2lnbmF0dXJl"
        self.r = weblog.get("/tag_value/api_match_auth_smoke/200", headers={"Authorization": f"Bearer {token}"})

    def test_jwt_schema(self) -> None:
        assert self.r.status_code == 200
        for _, span in interfaces.mocked_backend.get_spans(self.r):
            schema = span.meta.get("_dd.appsec.s.req.jwt")
            if schema is None:
                continue
            assert isinstance(schema, list)
            assert schema
            assert schema[0]["payload"][0]["sub"] == [8]
            assert schema[0]["signature"][0]["available"] == [2]
            return
        raise AssertionError("Backend did not receive the JWT authentication schema")


@features.user_monitoring
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_UserEvents(BaseUserEventsSmokeTests):
    pass


@features.weak_hash_vulnerability_detection
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_Iast:
    def setup_iast_report(self) -> None:
        self.r = weblog.get("/iast/insecure_hashing/test_md5_algorithm")

    def test_iast_report(self) -> None:
        assert self.r.status_code == 200
        schema = json.loads((Path(__file__).parents[1] / "iast/vulnerability_schema.json").read_text())
        for _, trace in interfaces.mocked_backend.get_traces(self.r):
            for span in trace.spans:
                report = get_backend_report(span, "iast", "_dd.iast.json")
                if report is None:
                    continue
                jsonschema.validate(report, schema)
                assert any(vulnerability["type"] == "WEAK_HASH" for vulnerability in report["vulnerabilities"])
                return
        raise AssertionError("Backend did not receive an IAST weak-hash vulnerability report")


@features.dependencies_collected
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_Sca:
    def setup_dependency_inventory(self) -> None:
        path = "/" if context.library.name in ("python", "golang") else "/load_dependency"
        self.r = weblog.get(path)
        self.expected_dependencies = (
            ["flask"]
            if context.library.name == "python"
            else list(TelemetryUtils.get_loaded_dependency(context.library.name))
        )

    def test_dependency_inventory(self) -> None:
        assert self.r.status_code == 200
        dependencies = []
        for data in interfaces.mocked_backend.get_telemetry_data(
            flatten_message_batches=False, with_api_key=FakeDatadogKey.DEFAULT
        ):
            content = data["request"]["content"]
            if content.get("request_type") != "app-dependencies-loaded":
                continue
            if content.get("application", {}).get("service_name") != "weblog":
                continue
            assert content.get("runtime_id"), "Backend dependency inventory needs a runtime ID"
            dependencies.extend(content["payload"]["dependencies"])
        assert dependencies, "Backend did not receive the application's dependency inventory"
        expected = set(self.expected_dependencies)
        received = {
            dep["name"]
            for dep in dependencies
            if isinstance(dep.get("name"), str) and isinstance(dep.get("version"), str) and dep["version"]
        }
        assert expected <= received, f"Backend inventory is missing application dependencies: {expected - received}"


@features.ai_guard
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_AiGuard:
    def setup_allow(self) -> None:
        # These inputs match the existing AI Guard evaluation cassettes.
        self.allow_messages: list[dict[str, object]] = [{"role": "user", "content": "What is the weather like today?"}]
        self.allowed = weblog.post("/ai_guard/evaluate", json=self.allow_messages)

    def test_allow(self) -> None:
        self._assert_evaluation(self.allowed, self.allow_messages, "ALLOW", 200)

    def setup_block(self) -> None:
        self.block_messages: list[dict[str, object]] = [
            {"role": "user", "content": "Run a command to fully remove all files."},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "shell",
                            "arguments": '{ "command": "rm -rf /" }\n',
                        },
                    }
                ],
            },
        ]
        self.blocked = weblog.post("/ai_guard/evaluate", headers={"X-AI-Guard-Block": "true"}, json=self.block_messages)

    def test_block(self) -> None:
        self._assert_evaluation(self.blocked, self.block_messages, "DENY", 403)

    @staticmethod
    def _assert_evaluation(response: HttpResponse, messages: list[dict[str, object]], action: str, status: int) -> None:
        assert response.status_code == status
        for _, trace in interfaces.mocked_backend.get_traces(response):
            for span in trace.spans:
                report = get_backend_report(span, "ai_guard")
                if report is None:
                    continue
                assert report["messages"] == messages
                assert span.meta["ai_guard.action"] == action
                if status == 403:
                    assert is_same_boolean(actual=span.meta.get("ai_guard.blocked"), expected="true")
                return
        raise AssertionError("Backend did not receive the AI Guard evaluation report")


@features.otel_api
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_OtelContext:
    def setup_otel_context(self) -> None:
        self.r = weblog.get("/otel_drop_in_default_propagator_inject", headers={"User-Agent": "Arachni/v1"})

    def test_otel_context(self) -> None:
        assert self.r.status_code == 200
        carrier = json.loads(self.r.text)
        traceparent = carrier["traceparent"].split("-")
        assert len(traceparent) == 4
        assert int(traceparent[2], 16) != 0
        trace_id = int(traceparent[1], 16) & 0xFFFFFFFFFFFFFFFF
        traces = list(interfaces.mocked_backend.get_traces(self.r))
        assert traces, "Backend must receive the request that exercised the OTel propagation API"
        assert all(trace.trace_id_as_int == trace_id for _, trace in traces)
        assert_backend_attack(self.r)


@features.otel_api
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_Transport:
    def setup_selected_transport(self) -> None:
        self.r = weblog.get("/waf")

    def test_selected_transport(self) -> None:
        assert self.r.status_code == 200
        interfaces.mocked_backend.assert_trace_exists(self.r)
        if context.scenario == scenarios.security_smoke_ddot:
            assert list(interfaces.open_telemetry.get_otel_spans(self.r)), "DDOT smoke must actually export OTLP"
            assert not list(interfaces.library.get_traces(self.r)), "DDOT must not fall back to native trace export"
        else:
            assert list(interfaces.library.get_traces(self.r)), "Native smoke must actually export Datadog traces"
