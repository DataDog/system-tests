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

        RC_PAYLOAD = {
            "client_configs": ["datadog/2/ASM_FEATURES/asm_features_activation/config"],
            "roots": [],
            "target_files": [
                {
                    "path": "datadog/2/ASM_FEATURES/asm_features_activation/config",
                    "raw": "eyJhc20iOnsiZW5hYmxlZCI6dHJ1ZX19",
                }
            ],
            "targets": "eyJzaWduZWQiOnsiX3R5cGUiOiJ0YXJnZXRzIiwiZXhwaXJlcyI6IjIwMjItMDktMTdUMTI6NDk6MTVaIiwic3BlY192ZXJzaW9uIjoiMS4wLjAiLCJjdXN0b20iOnsib3BhcXVlX2JhY2tlbmRfc3RhdGUiOiJhYWFhYSJ9LCJ0YXJnZXRzIjp7ImRhdGFkb2cvMi9BU01fRkVBVFVSRVMvYXNtX2ZlYXR1cmVzX2FjdGl2YXRpb24vY29uZmlnIjp7ImN1c3RvbSI6eyJ2IjoxfSwiaGFzaGVzIjp7InNoYTI1NiI6IjE1OTY1OGFiODViZTcyMDc3NjFhNDExMTE3MmIwMTU1ODM5NGJmYzc0YTFmZTFkMzE0ZjIwMjNmN2M2NTZkYiJ9LCJsZW5ndGgiOjI0fX0sInZlcnNpb24iOjF9LCJzaWduYXR1cmVzIjpbeyJrZXlpZCI6IlRFU1RfS0VZX0lEIiwic2lnIjoiNDJhMzk3ZjNiNzc5MjQwNzkwMDRhYmY5MzU1ZDQ0ODQ2ZDFlNWQ4MjYzNjIzMTdkZTJiZjhmZTVlODQ1N2NhZmMxMTZiNTcwZjI4MGRkYTVmNzI1Y2Y5ZjU1NmYyOGMzOTEyMmQzYzM0MDQ2YmMwYzYzODU5NWExM2JhMzliMDAifV19",
        }

        self.response_with_deactivated_waf = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})
        self.config_state = rc.send_command(raw_payload=RC_PAYLOAD)
        self.response_with_activated_waf = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_asm_features(self):
        activation_state = self.config_state["asm_features_activation"]
        assert activation_state["apply_state"] == rc.ApplyState.ACKNOWLEDGED, self.config_state
        interfaces.library.assert_no_appsec_event(self.response_with_deactivated_waf)
        interfaces.library.assert_waf_attack(self.response_with_activated_waf)
