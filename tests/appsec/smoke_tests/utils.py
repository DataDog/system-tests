# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Shared AAP smoke tests verifying payload carriers at backend intake."""

from utils import context, interfaces, remote_config as rc, weblog
from utils._weblog import HttpResponse
from utils.dd_constants import SamplingPriority
from utils.dd_types import DataDogAgentSpan, is_same_boolean
from utils.interfaces._open_telemetry import otlp_trace_id_to_hex

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


def assert_ddot_export(request: HttpResponse) -> None:
    accepted_ids = {
        f"0x{hex_id}"
        for tid in interfaces.open_telemetry.get_otel_trace_id(request, accepted_by="agent")
        if (hex_id := otlp_trace_id_to_hex(tid))
    }
    assert accepted_ids, "DDOT must accept an OTLP trace for this request"
    # Match by trace ID even if a native chunk lacks the root span, and by
    # request ID in case a fallback produced a new trace. Ignore non-trace traffic.
    rid = request.get_rid()
    for _, trace in interfaces.library.get_traces():
        message = f"Request {rid} was also exported via native trace intake ({trace.log_filename})"
        assert not any(trace.trace_id_equals(tid) for tid in accepted_ids), message
        assert not any(span.get_rid() == rid for span in trace), message


def _assert_numeric_metric(span: DataDogAgentSpan, name: str) -> float:
    value = span.metrics.get(name)
    assert isinstance(value, (int, float)), f"Backend should receive numeric {name}"
    assert not isinstance(value, bool), f"Backend should receive numeric {name}"
    assert value >= 0, name
    return float(value)


def _attack_spans(request: HttpResponse) -> list[DataDogAgentSpan]:
    spans = [
        span
        for _, span in interfaces.mocked_backend.get_spans(request)
        if is_same_boolean(actual=span.meta.get("appsec.event"), expected="true")
    ]
    assert spans, "Backend should receive the detected attack"
    for span in spans:
        assert span.get_sampling_priority() == SamplingPriority.USER_KEEP
    return spans


def _has_rule_in_all_reports(span: DataDogAgentSpan, rule_id: str) -> bool:
    reports = span.get_structured_payloads("appsec", "_dd.appsec.json")
    return bool(reports) and all(
        any(trigger.get("rule", {}).get("id") == rule_id for trigger in report.get("triggers", []))
        for report in reports
    )


def _assert_rasp_attack(
    response: HttpResponse,
    expected_rule: str,
    expected_params: dict[str, dict[str, str]],
    *,
    expect_stack: bool = True,
) -> None:
    """Verify RASP trigger, numeric timing metric, and linked exploit stack carriers at intake."""
    matched_span = False
    for span in _attack_spans(response):
        reports = span.get_structured_payloads("appsec", "_dd.appsec.json")
        assert reports, "Backend should receive an AppSec report"
        stack_ids: set[str] = set()
        for report in reports:
            matched_trigger = False
            for trigger in report.get("triggers", []):
                if trigger.get("rule", {}).get("id") != expected_rule:
                    continue
                for match in trigger.get("rule_matches", []):
                    for params in match.get("parameters", []):
                        if isinstance(params, dict) and all(
                            isinstance(params.get(name), dict)
                            and params[name].get("address") == fields.get("address")
                            and ("value" not in fields or params[name].get("value") == fields["value"])
                            for name, fields in expected_params.items()
                        ):
                            matched_trigger = True
                            if "stack_id" in trigger:
                                stack_ids.add(trigger["stack_id"])
            if not matched_trigger:
                break
        else:
            _assert_numeric_metric(span, "_dd.appsec.rasp.duration")
            if expect_stack:
                assert stack_ids, "RASP trigger should link to an exploit stack"
                stack_payloads = span.get_structured_payloads("_dd.stack")
                assert stack_payloads, "Backend should receive the _dd.stack carrier"
                for stack_payload in stack_payloads:
                    exploits = [s for s in stack_payload.get("exploit", []) if s.get("id") in stack_ids]
                    assert exploits, "Exploit stack ID should match the RASP trigger"
                    for stack in exploits:
                        assert isinstance(stack.get("language"), str)
                        assert stack["language"]
                        frames = stack.get("frames")
                        assert isinstance(frames, list)
                        assert 0 < len(frames) <= 32
            matched_span = True

    assert matched_span, f"No RASP attack found for rule {expected_rule}"


# ---------------------------------------------------------------------------
# Threats
# ---------------------------------------------------------------------------


class BaseThreatsSmokeTests:
    """Trigger a WAF attack and verify tags, retention, numeric metrics, and report carriers at intake."""

    _attack_response: HttpResponse | None = None

    @classmethod
    def _get_attack_response(cls) -> HttpResponse:
        if cls._attack_response is None:
            cls._attack_response = weblog.get(
                "/waf", headers={"User-Agent": "Arachni/v1", "X-Forwarded-For": "42.42.42.42"}
            )
        return cls._attack_response

    def setup_attack_detection_smoke(self) -> None:
        self.r = self._get_attack_response()

    def test_attack_detection_smoke(self) -> None:
        for span in _attack_spans(self.r):
            assert span.meta.get("http.client_ip") == "42.42.42.42"
            assert span.meta.get("http.request.headers.x-forwarded-for") == "42.42.42.42"
            assert span.meta.get("http.request.headers.user-agent", "").startswith("Arachni/v1")
            assert span.meta.get("_dd.runtime_family")
            assert _assert_numeric_metric(span, "_dd.appsec.enabled") == 1

            reports = span.get_structured_payloads("appsec", "_dd.appsec.json")
            assert reports, "Backend should receive an AppSec report"
            for report in reports:
                triggers = [trigger for trigger in report.get("triggers", []) if trigger["rule"]["id"] == "ua0-600-12x"]
                assert triggers, "Backend should receive the Arachni rule match"
                for trigger in triggers:
                    assert trigger["rule"]["tags"]["type"] in ("attack_tool", "security_scanner")
                    assert trigger["rule"]["tags"]["category"] == "attack_attempt"
                    assert trigger["rule_matches"], "Rule match details should reach intake"
                    for match in trigger["rule_matches"]:
                        assert match["operator"] == "match_regex"
                        assert match["operator_value"]
                        assert match["parameters"]
                        for parameter in match["parameters"]:
                            assert parameter["address"] == "server.request.headers.no_cookies"
                            assert parameter["key_path"][:1] == ["user-agent"]
                            assert parameter["value"].startswith("Arachni/v1")
                            assert parameter["highlight"]

    def setup_waf_monitoring_smoke(self) -> None:
        self.r = self._get_attack_response()

    def test_waf_monitoring_smoke(self) -> None:
        for span in _attack_spans(self.r):
            assert span.meta.get("_dd.appsec.event_rules.version")
            _assert_numeric_metric(span, "_dd.appsec.waf.duration")


# ---------------------------------------------------------------------------
# RASP
# ---------------------------------------------------------------------------


class BaseRaspSmokeTests:
    """Verify RASP attacks, timing metrics, and linked exploit stacks reach intake."""

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
            if content.get("request_type") == "generate-metrics":
                found_metrics = True
                for metric_series in content.get("payload", {}).get("series", []):
                    if metric_series.get("metric", "").startswith("waf."):
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

    def setup_remote_config_smoke(self) -> None:
        self.config_state = rc.tracer_rc_state.reset().set_config(*SMOKE_RC_RULE_FILE).apply().state
        self.r = weblog.get("/waf", headers={"X-Smoke-Test": "rc-smoke"})
        rc.tracer_rc_state.reset().apply()

    def test_remote_config_smoke(self) -> None:
        assert self.config_state == rc.ApplyState.ACKNOWLEDGED, (
            f"Remote config should be acknowledged, got {self.config_state}"
        )
        assert any(_has_rule_in_all_reports(span, SMOKE_RC_RULE_ID) for span in _attack_spans(self.r)), (
            "Agent should forward AppSec events for the RC-updated rule"
        )

    def setup_rasp_blocking_smoke(self) -> None:
        """Push RASP LFI blocking rule via RC, then trigger the attack."""
        rc.tracer_rc_state.reset().set_config(*SMOKE_RC_RULE_FILE).apply()
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})
        rc.tracer_rc_state.reset().apply()

    def test_rasp_blocking_smoke(self) -> None:
        assert self.r.status_code == 403
        _assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
            expect_stack=False,
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
        rc.tracer_rc_state.reset().set_config(*SMOKE_RC_RULE_FILE).set_config(
            "datadog/2/ASM_DATA/blocked_ips/config", config
        ).apply()
        self.r = weblog.get("/waf", headers={"X-Forwarded-For": "1.2.3.4"})
        rc.tracer_rc_state.reset().apply()

    def test_ip_blocking_smoke(self) -> None:
        assert self.r.status_code == 403
        assert any(_has_rule_in_all_reports(span, SMOKE_RC_IP_BLOCK_RULE_ID) for span in _attack_spans(self.r)), (
            "Agent should forward AppSec events for the blocked IP"
        )


# ---------------------------------------------------------------------------
# API Security
# ---------------------------------------------------------------------------


class BaseApiSecuritySmokeTests:
    """Verify compressed API security schema carriers are decoded at intake."""

    def setup_api_security_smoke(self) -> None:
        self.r = weblog.get("/waf", params={"smoke_query": "example"}, cookies={"smoke_cookie": "example"})

    def test_api_security_smoke(self) -> None:
        expected_fields = (
            ("req.headers", "user-agent"),
            ("req.query", "smoke_query"),
            ("req.cookies", "smoke_cookie"),
        )
        for _, span in interfaces.mocked_backend.get_spans(self.r):
            if not all(f"_dd.appsec.s.{address}" in span.meta for address, _ in expected_fields):
                continue
            for address, field in expected_fields:
                schema = span.meta[f"_dd.appsec.s.{address}"]
                assert isinstance(schema, list), f"Expected decoded schema list for {address}"
                assert schema, f"Expected decoded schema list for {address}"
                assert isinstance(schema[0], dict), f"Expected schema dict for {address}"
                assert isinstance(schema[0].get(field), list), f"Missing {field!r} in {address} schema"
            return

        raise AssertionError("Backend should receive decoded API Security request schemas")


# ---------------------------------------------------------------------------
# User Events
# ---------------------------------------------------------------------------


class BaseUserEventsSmokeTests:
    """Verify user login events reach intake."""

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
