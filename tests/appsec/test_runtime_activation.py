# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import bug
from utils import context
from utils import features
from utils import interfaces
from utils import remote_config as rc
from utils import scenarios
from utils import weblog
from utils.dd_constants import Capabilities


CONFIG_EMPTY = None  # Empty config to reset the state at test setup
CONFIG_ENABLED = {"asm": {"enabled": True}}


def _send_config(config: dict | None):
    if config is not None:
        rc.tracer_rc_state.set_config("datadog/2/ASM_FEATURES/asm_features_activation/config", config)
    else:
        rc.tracer_rc_state.reset()
    return rc.tracer_rc_state.apply().state


@scenarios.appsec_runtime_activation
@bug(context.library < "java@1.8.0" and context.appsec_rules_file is not None, reason="APMRP-360")
@features.changing_rules_using_rc
class Test_RuntimeActivation:
    """A library should block requests after AppSec is activated via remote config."""

    def setup_asm_features(self):
        self.reset_state = _send_config(CONFIG_EMPTY)
        self.response_with_deactivated_waf = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})
        self.config_state = _send_config(CONFIG_ENABLED)
        self.last_version = rc.tracer_rc_state.version
        self.response_with_activated_waf = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_asm_features(self):
        # ensure last config was applied
        assert self.reset_state == rc.ApplyState.ACKNOWLEDGED
        assert self.config_state == rc.ApplyState.ACKNOWLEDGED
        interfaces.library.assert_no_appsec_event(self.response_with_deactivated_waf)
        interfaces.library.assert_waf_attack(self.response_with_activated_waf)


@scenarios.appsec_runtime_activation
@features.changing_rules_using_rc
class Test_RuntimeDeactivation:
    """A library should stop blocking after Appsec is deactivated."""

    def setup_asm_features(self):
        self.response_with_activated_waf = []
        self.response_with_deactivated_waf = []
        self.config_states = []
        # deactivate and activate ASM 4 times
        for _ in range(4):
            self.config_states.append(_send_config(CONFIG_EMPTY))
            self.response_with_deactivated_waf.append(weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"}))

            self.config_states.append(_send_config(CONFIG_ENABLED))
            self.response_with_activated_waf.append(weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"}))

        self.config_states.append(_send_config(CONFIG_EMPTY))
        self.response_with_deactivated_waf.append(weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"}))

    def test_asm_features(self):
        # ensure last empty config was applied
        assert all(s == rc.ApplyState.ACKNOWLEDGED for s in self.config_states)
        for response in self.response_with_deactivated_waf:
            interfaces.library.assert_no_appsec_event(response)
        for response in self.response_with_activated_waf:
            interfaces.library.assert_waf_attack(response)


# Blocking capabilities reported as missing by the customer's Threat Protection panel:
# IP Blocking, User Blocking, In-App WAF (request) Blocking and Custom Rules.
BLOCKING_CAPABILITIES = {
    Capabilities.ASM_IP_BLOCKING,
    Capabilities.ASM_USER_BLOCKING,
    Capabilities.ASM_REQUEST_BLOCKING,
    Capabilities.ASM_CUSTOM_RULES,
}


@scenarios.appsec_runtime_activation
@features.changing_rules_using_rc
class Test_RuntimeActivationCapabilities:
    """The advertised RC capabilities must follow one-click (remote) activation/deactivation.

    Regression test for APPSEC-69019: when AppSec is enabled via remote activation instead of
    DD_APPSEC_ENABLED, the blocking RC capabilities (IP, user, in-app WAF, custom rules) were
    never advertised, so the Threat Protection panel wrongly reported "UPDATE REQUIRED". The
    blocking capabilities must be advertised only while AppSec is active: absent before
    activation, present after activation, and dropped again after deactivation.
    """

    def setup_capabilities(self):
        self.disabled_state = _send_config(CONFIG_EMPTY)
        self.version_disabled_before = rc.tracer_rc_state.version
        self.enabled_state = _send_config(CONFIG_ENABLED)
        self.version_enabled = rc.tracer_rc_state.version
        self.deactivated_state = _send_config(CONFIG_EMPTY)
        self.version_disabled_after = rc.tracer_rc_state.version

    def test_capabilities(self):
        assert self.disabled_state == rc.ApplyState.ACKNOWLEDGED
        assert self.enabled_state == rc.ApplyState.ACKNOWLEDGED
        assert self.deactivated_state == rc.ApplyState.ACKNOWLEDGED

        # Before activation: AppSec can be remotely activated, but blocking is not advertised yet.
        caps_before = interfaces.library.get_rc_capabilities(self.version_disabled_before)
        assert Capabilities.ASM_ACTIVATION in caps_before
        assert not (BLOCKING_CAPABILITIES & caps_before), (
            f"blocking capabilities advertised before activation: {BLOCKING_CAPABILITIES & caps_before}"
        )

        # After one-click activation: all blocking capabilities must be advertised.
        caps_enabled = interfaces.library.get_rc_capabilities(self.version_enabled)
        assert caps_enabled >= BLOCKING_CAPABILITIES, (
            f"blocking capabilities missing after activation: {BLOCKING_CAPABILITIES - caps_enabled}"
        )

        # After deactivation: blocking capabilities must be dropped, activation still advertised.
        caps_after = interfaces.library.get_rc_capabilities(self.version_disabled_after)
        assert Capabilities.ASM_ACTIVATION in caps_after
        assert not (BLOCKING_CAPABILITIES & caps_after), (
            f"blocking capabilities still advertised after deactivation: {BLOCKING_CAPABILITIES & caps_after}"
        )
