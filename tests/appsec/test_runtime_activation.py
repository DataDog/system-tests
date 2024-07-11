# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, context, interfaces, scenarios, bug, features, remote_config as rc


# dd.rc.targets.key.id=TEST_KEY_ID
# dd.rc.targets.key=1def0961206a759b09ccdf2e622be20edf6e27141070e7b164b7e16e96cf402c
# private key: a78bd01afe0dc0baa6904e1b65448a6bbe160e07f7fc375c3bcb3ec08f008cc5


@scenarios.appsec_runtime_activation
@bug(
    context.library < "java@1.8.0" and context.appsec_rules_file is not None,
    reason="ASM_FEATURES was not subscribed when a custom rules file was present",
)
@bug(context.library == "java@1.6.0", reason="https://github.com/DataDog/dd-trace-java/pull/4614")
@features.appsec_request_blocking
class Test_RuntimeActivation:
    """A library should block requests after AppSec is activated via remote config."""

    def setup_asm_features(self):
        command = rc.RemoteConfigCommand(version=1)

        config = {"asm":{"enabled":True}}

        command.add_client_config("datadog/2/ASM_FEATURES/asm_features_activation/config", config)


        self.response_with_deactivated_waf = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})
        self.config_state = command.send()
        self.response_with_activated_waf = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_asm_features(self):
        activation_state = self.config_state["asm_features_activation"]
        assert activation_state["apply_state"] == rc.ApplyState.ACKNOWLEDGED, self.config_state
        interfaces.library.assert_no_appsec_event(self.response_with_deactivated_waf)
        interfaces.library.assert_waf_attack(self.response_with_activated_waf)
