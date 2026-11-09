"""Security product contracts at backend intake, shared by all three topologies."""

import json
from pathlib import Path

import jsonschema

from utils import context, features, interfaces, remote_config as rc, scenarios, weblog
from utils.dd_types import is_same_boolean
from utils._weblog import HttpResponse
from utils._context._scenarios._core import FakeDatadogKey
from utils.telemetry_utils import TelemetryUtils
from tests.appsec.smoke_tests.utils import (
    BaseApiSecuritySmokeTests,
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


@features.rasp_local_file_inclusion
@features.rasp_server_side_request_forgery
@features.rasp_sql_injection
@features.rasp_shell_injection
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_Rasp(BaseRaspSmokeTests):
    pass


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


@features.api_security_schemas
@scenarios.security_smoke
@scenarios.security_smoke_otel_api
@scenarios.security_smoke_ddot
class Test_SecuritySmoke_ApiSecurity(BaseApiSecuritySmokeTests):
    pass


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
