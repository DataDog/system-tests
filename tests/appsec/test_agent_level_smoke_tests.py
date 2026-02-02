# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""AppSec smoke tests for the appsec_apm_standalone scenario."""

from utils import features, interfaces, remote_config as rc, rfc, scenario_groups, weblog

SMOKE_RC_RULE_ID = "smoke-rc-0001"
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
            }
        ],
    },
)


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@scenario_groups.appsec_smoke_tests
@features.rasp_local_file_inclusion
class Test_Lfi_UrlQuery:
    def setup_lfi_get(self) -> None:
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_get(self) -> None:
        assert self.r.status_code == 200

        interfaces.agent.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )


@rfc("https://docs.google.com/document/d/1D4hkC0jwwUyeo0hEQgyKP54kM1LZU98GL8MaP60tQrA")
@scenario_groups.appsec_smoke_tests
@features.api_security_schemas
class Test_Smoke_API_Security:
    def setup_api_security_smoke(self) -> None:
        self.r = weblog.get("/waf")

    def test_api_security_smoke(self) -> None:
        assert any(
            any(key.startswith("_dd.appsec.s.") for key in interfaces.agent.get_span_meta(span, span_format))
            for _, span, span_format in interfaces.agent.get_spans(self.r)
        )


@rfc("https://docs.google.com/document/d/1D4hkC0jwwUyeo0hEQgyKP54kM1LZU98GL8MaP60tQrA")
@scenario_groups.appsec_smoke_tests
@features.waf_telemetry
class Test_Smoke_Telemetry:
    def setup_telemetry_smoke(self) -> None:
        weblog.get("/")
        self.r = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})

    def test_telemetry_smoke(self) -> None:
        telemetry_data = list(interfaces.agent.get_telemetry_data(flatten_message_batches=False))

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


@rfc("https://docs.google.com/document/d/1Ig5lna4l57-tJLMnC76noGFJaIHvudfYXdZYKz6gXUo")
@scenario_groups.appsec_smoke_tests
@features.changing_rules_using_rc
class Test_Smoke_Remote_Config:
    def setup_remote_config_smoke(self) -> None:
        self.config_state = rc.tracer_rc_state.reset().set_config(*SMOKE_RC_RULE_FILE).apply().state
        self.r = weblog.get("/waf", headers={"X-Smoke-Test": "rc-smoke"})

    def test_remote_config_smoke(self) -> None:
        assert self.config_state == rc.ApplyState.ACKNOWLEDGED, (
            f"Remote config should be acknowledged, got {self.config_state}"
        )

        assert any(
            interfaces.agent.get_span_meta(span, span_format).get("appsec.event") == "true"
            and any(
                trigger.get("rule", {}).get("id") == SMOKE_RC_RULE_ID for trigger in appsec_data.get("triggers", [])
            )
            for _, span, span_format, appsec_data in interfaces.agent.get_appsec_events(self.r)
        ), "Agent should forward AppSec events for the RC-updated rule"


@scenario_groups.appsec_smoke_tests
@features.security_events_metadata
class Test_Smoke_Basic_Attack_Detection:
    def setup_attack_detection_smoke(self) -> None:
        rc.tracer_rc_state.reset().apply()
        self.r = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})

    def test_attack_detection_smoke(self) -> None:
        found_attack = False
        has_waf_version = False
        has_appsec_data = False

        for _, span, span_format, appsec_data in interfaces.agent.get_appsec_events(self.r):
            meta = interfaces.agent.get_span_meta(span, span_format)
            if meta.get("appsec.event") == "true":
                found_attack = True

                if "_dd.appsec.waf.version" in meta:
                    has_waf_version = True

                if appsec_data is not None:
                    has_appsec_data = True

                if has_waf_version and has_appsec_data:
                    break

        assert found_attack, "Agent should forward detected attacks in span metadata"
        assert has_waf_version, "Agent spans should include WAF version metadata"
        assert has_appsec_data, "Agent spans should include AppSec payload (JSON or metastruct)"
