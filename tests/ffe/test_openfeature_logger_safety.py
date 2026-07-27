"""Test that application error handlers cannot break OpenFeature evaluation."""

import json

from utils import context
from utils import features
from utils import irrelevant
from utils import remote_config as rc
from utils import scenarios
from utils import weblog


RC_PRODUCT = "FFE_FLAGS"
RC_PATH = f"datadog/2/{RC_PRODUCT}"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_dynamic_evaluation
@irrelevant(context.library != "php", reason="This test covers the PHP OpenFeature endpoint contract")
class Test_FFE_OpenFeature_Logger_Safety:
    """The PHP weblog must keep the OpenFeature endpoint contract on every supported PHP runtime."""

    def setup_openfeature_logger_safety(self) -> None:
        self.flag_key = "openfeature-logger-safety"
        config = {
            "createdAt": "2024-04-17T19:40:53.716Z",
            "format": "SERVER",
            "environment": {"name": "Test"},
            "flags": {
                self.flag_key: {
                    "key": self.flag_key,
                    "enabled": True,
                    "variationType": "BOOLEAN",
                    "variations": {
                        "on": {"key": "on", "value": True},
                        "off": {"key": "off", "value": False},
                    },
                    "allocations": [
                        {
                            "key": "default-allocation",
                            "rules": [],
                            "splits": [{"variationKey": "on", "shards": []}],
                            "doLog": False,
                        }
                    ],
                }
            },
        }
        rc.tracer_rc_state.reset().set_config(f"{RC_PATH}/openfeature-logger-safety/config", config).apply()

        self.response = weblog.post(
            "/ffe",
            json={
                "flag": self.flag_key,
                "variationType": "BOOLEAN",
                "defaultValue": False,
                "targetingKey": "customer-request",
                "attributes": {},
                "evaluationApi": "openfeature",
            },
        )

    def test_openfeature_logger_safety(self) -> None:
        assert self.response.status_code == 200, f"Flag evaluation failed: {self.response.text}"
        result = json.loads(self.response.text)

        required_fields = {"value", "reason", "variant", "errorCode", "errorMessage", "providerState"}
        assert required_fields <= result.keys(), f"OpenFeature response does not satisfy the /ffe contract: {result}"

        if "-7." in context.weblog_variant:
            assert result["value"] is False, f"PHP 7 must return the supplied default value: {result}"
            assert result["reason"] == "ERROR", f"PHP 7 must return an OpenFeature error result: {result}"
            assert result["errorCode"] == "PROVIDER_NOT_READY", (
                f"PHP 7 must report that the OpenFeature provider is unavailable: {result}"
            )
            assert result["errorMessage"], f"PHP 7 must explain why the OpenFeature provider is unavailable: {result}"
            return

        assert result["value"] is True, (
            "The OpenFeature provider returned the code default after application error handling "
            f"promoted a provider log to an exception: {result}"
        )
        assert result["reason"] == "STATIC", f"Expected STATIC resolution details: {result}"
        assert result["errorCode"] is None, f"Expected no OpenFeature resolution error: {result}"
