# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""AppSec smoke tests for the appsec_apm_standalone scenario."""

from utils import features, interfaces, remote_config as rc, weblog, scenarios

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


class AgentLevelSmokeTests:
    def setup_lfi_smoke(self) -> None:
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_smoke(self) -> None:
        assert self.r.status_code == 200

        interfaces.agent.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )

    def setup_api_security_smoke(self) -> None:
        self.r = weblog.get("/waf")

    def test_api_security_smoke(self) -> None:
        assert any(
            any(key.startswith("_dd.appsec.s.") for key in span.meta) for _, span in interfaces.agent.get_spans(self.r)
        )

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

    def setup_remote_config_smoke(self) -> None:
        self.config_state = rc.tracer_rc_state.reset().set_config(*SMOKE_RC_RULE_FILE).apply().state
        self.r = weblog.get("/waf", headers={"X-Smoke-Test": "rc-smoke"})

    def test_remote_config_smoke(self) -> None:
        assert self.config_state == rc.ApplyState.ACKNOWLEDGED, (
            f"Remote config should be acknowledged, got {self.config_state}"
        )

        assert any(
            span.meta.get("appsec.event") == "true"
            and any(
                trigger.get("rule", {}).get("id") == SMOKE_RC_RULE_ID for trigger in appsec_data.get("triggers", [])
            )
            for _, span, appsec_data in interfaces.agent.get_appsec_data(self.r)
        ), "Agent should forward AppSec events for the RC-updated rule"

    def setup_attack_detection_smoke(self) -> None:
        rc.tracer_rc_state.reset().apply()
        self.r = weblog.get("/waf", headers={"User-Agent": "Arachni/v1"})

    def test_attack_detection_smoke(self) -> None:
        found_attack = False
        has_appsec_data = False

        for _, span, appsec_data in interfaces.agent.get_appsec_data(self.r):
            span_meta = span.get("meta", {}) or span.get("attributes", {})
            if span_meta.get("appsec.event") == "true":
                found_attack = True

                if appsec_data is not None:
                    has_appsec_data = True
                    break

        assert found_attack, "Agent should forward detected attacks in span metadata"
        assert has_appsec_data, "Agent spans should include AppSec payload (JSON or metastruct)"


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone(AgentLevelSmokeTests):
    pass
