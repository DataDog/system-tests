# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Shared AppSec smoke assertions at backend intake."""

from utils import context, interfaces, remote_config as rc, weblog
from utils.dd_types import DataDogAgentSpan, is_same_boolean
from typing import Any
from utils._weblog import HttpResponse

SMOKE_RC_RULE_ID = "smoke-rc-0001"
SMOKE_RC_RASP_RULE_ID = "rasp-930-100"
SMOKE_RC_IP_BLOCK_RULE_ID = "blk-001-001"
SMOKE_RC_RULE_FILE: tuple[str, dict[str, object]] = (
    "datadog/2/ASM_DD/rules/config",
    {
        "version": "2.2",
        "metadata": {"rules_version": "2.71.8182"},
        "rules": [
            {
                "id": SMOKE_RC_RULE_ID,
                "name": "Smoke RC rule",
                "tags": {
                    "type": "attack_tool",
                    "category": "attack_attempt",
                    "confidence": "1",
                },
                "conditions": [
                    {
                        "parameters": {
                            "inputs": [
                                {
                                    "address": "server.request.headers.no_cookies",
                                    "key_path": ["x-smoke-test"],
                                }
                            ],
                            "regex": "^rc-smoke$",
                        },
                        "operator": "match_regex",
                    }
                ],
                "transformers": [],
            },
            {
                "id": SMOKE_RC_RASP_RULE_ID,
                "name": "Local file inclusion exploit",
                "tags": {
                    "type": "lfi",
                    "category": "vulnerability_trigger",
                    "confidence": "0",
                    "module": "rasp",
                },
                "conditions": [
                    {
                        "parameters": {
                            "resource": [{"address": "server.io.fs.file"}],
                            "params": [
                                {"address": "server.request.query"},
                                {"address": "server.request.body"},
                                {"address": "server.request.path_params"},
                            ],
                        },
                        "operator": "lfi_detector",
                    }
                ],
                "transformers": [],
                "on_match": ["block"],
            },
            {
                "id": SMOKE_RC_IP_BLOCK_RULE_ID,
                "name": "Block IP Addresses",
                "tags": {
                    "type": "block_ip",
                    "category": "security_response",
                },
                "conditions": [
                    {
                        "parameters": {
                            "inputs": [{"address": "http.client_ip"}],
                            "data": "blocked_ips",
                        },
                        "operator": "ip_match",
                    }
                ],
                "transformers": [],
                "on_match": ["block"],
            },
        ],
    },
)


def get_backend_report(span: DataDogAgentSpan, name: str, json_tag: str | None = None) -> dict[str, Any] | None:
    """Read decoded intake fields; ordinary string metadata is not a structured report."""
    report = span.get("metaStruct", {}).get(name)
    if report is None:
        # Efficient Agent payloads carry structured bytes in the typed attributes map.
        report = span.meta.get(name)
    if report is None and json_tag is not None:
        report = span.meta.get(json_tag)
    if report is not None:
        assert isinstance(report, dict), f"Backend must receive a structured {name} report, got {type(report).__name__}"
    return report


def assert_backend_attack(response: HttpResponse) -> None:
    for _, span, _ in interfaces.mocked_backend.get_appsec_data(response):
        report = get_backend_report(span, "appsec", "_dd.appsec.json")
        assert report is not None
        if is_same_boolean(actual=span.meta.get("appsec.event"), expected="true"):
            triggers = report.get("triggers")
            assert isinstance(triggers, list), "Backend AppSec triggers must be an array"
            assert triggers, "Backend AppSec report must include attack triggers"
            assert all(
                isinstance(trigger.get("rule", {}).get("id"), str) and trigger["rule"]["id"] for trigger in triggers
            )
            return
    raise AssertionError("Backend did not receive an AppSec event with a structured attack report")


def _assert_rasp_attack(response: HttpResponse, expected_rule: str, expected_params: dict[str, dict[str, str]]) -> None:
    """Walk agent appsec data and assert the expected RASP rule triggered."""
    for _, span, _ in interfaces.mocked_backend.get_appsec_data(response):
        appsec_data = get_backend_report(span, "appsec", "_dd.appsec.json")
        assert appsec_data is not None
        for trigger in appsec_data.get("triggers", []):
            if trigger.get("rule", {}).get("id") != expected_rule:
                continue
            for match in trigger.get("rule_matches", []):
                for params in match.get("parameters", []):
                    if not isinstance(params, dict):
                        continue
                    if all(
                        isinstance(params.get(name), dict)
                        and params[name].get("address") == fields.get("address")
                        and ("value" not in fields or params[name].get("value") == fields["value"])
                        for name, fields in expected_params.items()
                    ):
                        return

    raise AssertionError(f"No RASP attack found for rule {expected_rule}")


# ---------------------------------------------------------------------------
# Threats
# ---------------------------------------------------------------------------


class BaseThreatsSmokeTests:
    """Verify basic WAF attack detection is forwarded by the agent."""

    _rc_state = rc.tracer_rc_state

    def setup_attack_detection_smoke(self) -> None:
        self._rc_state.reset().apply()
        self.r = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})

    def test_attack_detection_smoke(self) -> None:
        assert_backend_attack(self.r)


# ---------------------------------------------------------------------------
# RASP
# ---------------------------------------------------------------------------


class BaseRaspSmokeTests:
    """Verify RASP attacks are detected and forwarded by the agent."""

    def setup_lfi_smoke(self) -> None:
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_smoke(self) -> None:
        _assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )

    def setup_ssrf_smoke(self) -> None:
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_smoke(self) -> None:
        _assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {"address": "server.io.net.url"},
                "params": {"address": "server.request.query", "value": "169.254.169.254"},
            },
        )

    def setup_sqli_smoke(self) -> None:
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1=1 --"})

    def test_sqli_smoke(self) -> None:
        _assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement"},
                "params": {"address": "server.request.query", "value": "' OR 1=1 --"},
            },
        )

    def setup_shi_smoke(self) -> None:
        self.r = weblog.get("/rasp/shi", params={"list_dir": "$(cat /etc/passwd)"})

    def test_shi_smoke(self) -> None:
        _assert_rasp_attack(
            self.r,
            "rasp-932-100",
            {
                "resource": {"address": "server.sys.shell.cmd"},
                "params": {"address": "server.request.query", "value": "$(cat /etc/passwd)"},
            },
        )


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


class BaseTelemetrySmokeTests:
    """Verify telemetry metrics are forwarded by the agent."""

    def setup_telemetry_smoke(self) -> None:
        weblog.get("/")
        self.r = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})

    def test_telemetry_smoke(self) -> None:
        telemetry_data = list(interfaces.mocked_backend.get_telemetry_data(flatten_message_batches=False))

        assert telemetry_data, "Agent should forward telemetry data from the library"

        found_metrics = False
        found_waf_metric = False

        for data in telemetry_data:
            content = data.get("request", {}).get("content", {})
            request_type = content.get("request_type")

            if request_type == "generate-metrics":
                found_metrics = True

                payload = content.get("payload", {})
                series = payload.get("series", [])

                for metric_series in series:
                    metric_name = metric_series.get("metric", "")
                    if metric_name.startswith("waf."):
                        found_waf_metric = True
                        break

            if found_metrics and found_waf_metric:
                break

        assert found_metrics
        assert found_waf_metric


# ---------------------------------------------------------------------------
# Remote Config
# ---------------------------------------------------------------------------


class BaseRemoteConfigSmokeTests:
    """Verify remote config rules are acknowledged, applied, and can block."""

    _rc_state = rc.tracer_rc_state

    def setup_remote_config_smoke(self) -> None:
        self.config_state = self._rc_state.reset().set_config(*SMOKE_RC_RULE_FILE).apply().state
        self.r = weblog.get("/waf", headers={"X-Smoke-Test": "rc-smoke"})
        self._rc_state.reset().apply()

    def test_remote_config_smoke(self) -> None:
        assert self.config_state == rc.ApplyState.ACKNOWLEDGED, (
            f"Remote config should be acknowledged, got {self.config_state}"
        )

        for _, span, _ in interfaces.mocked_backend.get_appsec_data(self.r):
            report = get_backend_report(span, "appsec", "_dd.appsec.json")
            assert report is not None
            if is_same_boolean(actual=span.meta.get("appsec.event"), expected="true") and any(
                trigger.get("rule", {}).get("id") == SMOKE_RC_RULE_ID for trigger in report.get("triggers", [])
            ):
                return
        raise AssertionError("Backend did not receive an AppSec event for the RC-updated rule")

    def setup_rasp_blocking_smoke(self) -> None:
        """Push RASP LFI blocking rule via RC, then trigger the attack."""
        self._rc_state.reset().set_config(*SMOKE_RC_RULE_FILE).apply()
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})
        self._rc_state.reset().apply()

    def test_rasp_blocking_smoke(self) -> None:
        assert self.r.status_code == 403
        _assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )

    def setup_ip_blocking_smoke(self) -> None:
        config = {
            "rules_data": [
                {
                    "id": "blocked_ips",
                    "type": "ip_with_expiration",
                    "data": [{"value": "1.2.3.4", "expiration": 9999999999}],
                }
            ]
        }
        self._rc_state.reset().set_config(*SMOKE_RC_RULE_FILE).set_config(
            "datadog/2/ASM_DATA/blocked_ips/config", config
        ).apply()
        self.r = weblog.get("/waf", headers={"X-Forwarded-For": "1.2.3.4"})
        self._rc_state.reset().apply()

    def test_ip_blocking_smoke(self) -> None:
        assert self.r.status_code == 403


# ---------------------------------------------------------------------------
# API Security
# ---------------------------------------------------------------------------


class BaseApiSecuritySmokeTests:
    """Verify API security schemas are collected and forwarded."""

    def setup_api_security_smoke(self) -> None:
        self.r = weblog.get("/waf")

    def test_api_security_smoke(self) -> None:
        for _, span in interfaces.mocked_backend.get_spans(self.r):
            schema = span.meta.get("_dd.appsec.s.req.headers")
            if schema is None:
                continue
            assert span.meta.get("http.method") == "GET", "Backend API schemas need the request method"
            assert isinstance(schema, list), "Backend schema must be an array"
            assert schema, "Backend schema must not be empty"
            assert isinstance(schema[0], dict), "Backend header schema must describe an object"
            user_agent_schema = schema[0].get("user-agent")
            assert isinstance(user_agent_schema, list)
            assert user_agent_schema[0] == 8, "Backend schema must describe the request's user-agent string"
            return
        raise AssertionError("Backend did not receive a request header schema")


# ---------------------------------------------------------------------------
# User Events
# ---------------------------------------------------------------------------


class BaseUserEventsSmokeTests:
    """Verify user login events are tracked in standalone mode."""

    def setup_login_success_smoke(self) -> None:
        username_key = "user[username]" if "rails" in context.weblog_variant else "username"
        password_key = "user[password]" if "rails" in context.weblog_variant else "password"
        self.r = weblog.post("/login?auth=local", data={username_key: "test", password_key: "1234"})

    def test_login_success_smoke(self) -> None:
        for _, span in interfaces.mocked_backend.get_spans(self.r):
            meta = span.meta
            if meta.get("_dd.appsec.usr.login") or meta.get("appsec.events.users.login.success.usr.login"):
                return

        raise AssertionError("Agent spans should include user login event tags")
