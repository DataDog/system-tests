# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, coverage, interfaces, released, irrelevant

# dd.rc.targets.key.id=TEST_KEY_ID
# dd.rc.targets.key=1def0961206a759b09ccdf2e622be20edf6e27141070e7b164b7e16e96cf402c
# private key: a78bd01afe0dc0baa6904e1b65448a6bbe160e07f7fc375c3bcb3ec08f008cc5


@released(java="0.115.0", cpp="?", dotnet="2.16.0", php="?", python="?", ruby="?", nodejs="3.9.0", golang="?")
@irrelevant(context.appsec_rules_file == "")
@coverage.basic
class Test_RuntimeActivation(BaseTestCase):
    """A library should block requests after AppSec is activated via remote config."""

    def test_asm_features(self):
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

        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.assert_waf_attack(r)
