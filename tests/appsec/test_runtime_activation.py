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


CONFIG_EMPTY = None  # Empty config to reset the state at test setup
CONFIG_ENABLED = {"asm": {"enabled": True}}


def _send_config(config: dict | None):
    if config is not None:
        rc.rc_state.set_config("datadog/2/ASM_FEATURES/asm_features_activation/config", config)
    else:
        rc.rc_state.reset()
    return rc.rc_state.apply().state


@scenarios.appsec_runtime_activation
@bug(context.library < "java@1.8.0" and context.appsec_rules_file is not None, reason="APMRP-360")
@bug(context.library == "java@1.6.0", reason="APMRP-360")
@features.changing_rules_using_rc
class Test_RuntimeActivation:
    """A library should block requests after AppSec is activated via remote config."""

    def setup_asm_features(self):
        self.reset_state = _send_config(CONFIG_EMPTY)
        self.response_with_deactivated_waf = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})
        self.config_state = _send_config(CONFIG_ENABLED)
        self.last_version = rc.rc_state.version
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
