"""Native AAP contracts at backend intake."""

from utils import features, interfaces, remote_config as rc, scenarios, weblog
from utils.dd_types import is_same_boolean
from tests.appsec.smoke_tests.utils import (
    BaseThreatsSmokeTests,
    BaseTelemetrySmokeTests,
    BaseUserEventsSmokeTests,
    SMOKE_RC_RULE_FILE,
    SMOKE_RC_RULE_ID,
    SMOKE_RC_IP_BLOCK_RULE_ID,
    assert_backend_attack,
    assert_backend_blocked,
    assert_backend_security_data,
    wait_for_config_acknowledged,
)


@features.security_events_metadata
@scenarios.security_smoke
class Test_SecuritySmoke_Threats(BaseThreatsSmokeTests):
    _rc_state = rc.backend_rc_state


@features.security_events_metadata
@scenarios.security_smoke
class Test_SecuritySmoke_EventTags:
    def setup_event_tags(self) -> None:
        self.r = weblog.get("/waf", headers={"User-Agent": "Arachni/v1", "X-Forwarded-For": "42.42.42.42"})

    def test_event_tags(self) -> None:
        assert_backend_security_data()
        spans = [
            span
            for _, span in interfaces.mocked_backend.get_spans(self.r)
            if is_same_boolean(actual=span.meta.get("appsec.event"), expected="true")
        ]
        assert spans, "Backend did not receive a security event"
        for span in spans:
            assert span.metrics.get("_dd.appsec.enabled") == 1
            assert span.meta.get("http.client_ip") == "42.42.42.42"
            assert span.meta.get("network.client.ip")
            assert "42.42.42.42" in span.meta.get("http.request.headers.x-forwarded-for", "")
            assert "Arachni/v1" in span.meta.get("http.request.headers.user-agent", "")
            assert span.meta.get("http.response.headers.content-type")
            for tag in ("_dd.appsec.event_rules.version", "_dd.runtime_family"):
                assert isinstance(span.meta.get(tag), str), f"Missing backend tag {tag}"
                assert span.meta[tag], f"Empty backend tag {tag}"
            duration = span.metrics.get("_dd.appsec.waf.duration")
            assert isinstance(duration, (int, float))
            assert duration >= 0
        # WAF version is initialization metadata, reported at least once per runtime.
        assert any(
            isinstance(span.meta.get("_dd.appsec.waf.version"), str) and span.meta["_dd.appsec.waf.version"]
            for _, span in interfaces.mocked_backend.get_spans()
            if span.get_span_service() == "weblog"
        ), "Backend did not receive the WAF version"


@features.waf_telemetry
@scenarios.security_smoke
class Test_SecuritySmoke_Telemetry(BaseTelemetrySmokeTests):
    pass


@features.user_monitoring
@scenarios.security_smoke
class Test_SecuritySmoke_UserEvents(BaseUserEventsSmokeTests):
    pass


@features.changing_rules_using_rc
@scenarios.security_smoke
class Test_SecuritySmoke_RemoteConfig:
    def setup_remote_config_smoke(self) -> None:
        state = rc.backend_rc_state
        try:
            self.config = state.reset().set_config(*SMOKE_RC_RULE_FILE).apply()
            self.acknowledged = wait_for_config_acknowledged(self.config, "rules")
            self.r = weblog.get("/waf", headers={"X-Smoke-Test": "rc-smoke"}) if self.acknowledged else None
        finally:
            state.reset().apply()

    def test_remote_config_smoke(self) -> None:
        assert self.acknowledged, "Tracer must acknowledge the rule version before attack traffic"
        assert self.r is not None
        assert_backend_attack(self.r, rule_id=SMOKE_RC_RULE_ID)


@features.appsec_request_blocking
@scenarios.security_smoke
class Test_SecuritySmoke_IpBlocking:
    def setup_ip_blocking_smoke(self) -> None:
        state = rc.backend_rc_state
        config = {
            "rules_data": [
                {
                    "id": "blocked_ips",
                    "type": "ip_with_expiration",
                    "data": [{"value": "1.2.3.4", "expiration": 9999999999}],
                }
            ]
        }
        try:
            self.config = (
                state.reset()
                .set_config(*SMOKE_RC_RULE_FILE)
                .set_config("datadog/2/ASM_DATA/blocked_ips/config", config)
                .apply()
            )
            self.rules_acknowledged = wait_for_config_acknowledged(self.config, "rules")
            self.data_acknowledged = wait_for_config_acknowledged(self.config, "blocked_ips")
            self.r = (
                weblog.get("/waf", headers={"X-Forwarded-For": "1.2.3.4"})
                if self.rules_acknowledged and self.data_acknowledged
                else None
            )
        finally:
            state.reset().apply()

    def test_ip_blocking_smoke(self) -> None:
        assert self.rules_acknowledged, "Tracer must acknowledge the blocking rule"
        assert self.data_acknowledged, "Tracer must acknowledge the blocked IP before attack traffic"
        assert self.r is not None
        assert_backend_attack(self.r, rule_id=SMOKE_RC_IP_BLOCK_RULE_ID)
        assert_backend_blocked(self.r)
