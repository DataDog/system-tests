# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, context, interfaces, scenarios, bug, features


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
        def remote_config_asm_payload(data):
            if data["path"] == "/v0.7/config":
                config_states = (
                    data.get("request", {})
                    .get("content", {})
                    .get("client", {})
                    .get("state", {})
                    .get("config_states", [])
                )
                return any(st["product"] == "ASM_FEATURES" and st["apply_state"] == 2 for st in config_states)

        interfaces.library.wait_for(remote_config_asm_payload, timeout=30)

        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_asm_features(self):
        interfaces.library.assert_waf_attack(self.r)
