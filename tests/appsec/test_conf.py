# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, context, interfaces, missing_feature, irrelevant, rfc, features
from utils.tools import nested_lookup
from utils.dd_constants import PYTHON_RELEASE_GA_1_1
from utils._context._scenarios.dynamic import dynamic_scenario


TELEMETRY_REQUEST_TYPE_GENERATE_METRICS = "generate-metrics"


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2355333252/Environment+Variables")
@features.threats_configuration
class Test_ConfigurationVariables:
    """Configuration environment variables"""

    SECRET = "This-value-is-secret"

    # this value is defined in DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP
    SECRET_WITH_HIDDEN_VALUE = "hide_value"

    def setup_enabled(self):
        self.r_enabled = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_enabled(self):
        """Test DD_APPSEC_ENABLED = true"""
        interfaces.library.assert_waf_attack(self.r_enabled)

    def setup_disabled(self):
        self.r_disabled = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    @irrelevant(library="ruby", weblog_variant="rack", reason="it's not possible to auto instrument with rack")
    @missing_feature("sinatra" in context.weblog_variant, reason="Sinatra endpoint not implemented")
    @dynamic_scenario(mandatory={"DD_APPSEC_ENABLED": "false", "DD_DBM_PROPAGATION_MODE": "disabled"})
    def test_disabled(self):
        """Test DD_APPSEC_ENABLED = false"""
        assert self.r_disabled.status_code == 200
        interfaces.library.assert_no_appsec_event(self.r_disabled)

    def setup_appsec_rules(self):
        self.r_appsec_rules = weblog.get("/waf", headers={"attack": "dedicated-value-for-testing-purpose"})

    @dynamic_scenario(mandatory={"DD_APPSEC_RULES": "/appsec_custom_rules.json"})
    def test_appsec_rules(self):
        """Test DD_APPSEC_RULES = custom rules file"""
        interfaces.library.assert_waf_attack(self.r_appsec_rules, pattern="dedicated-value-for-testing-purpose")

    def setup_waf_timeout(self):
        long_payload = "?" + "&".join(
            f"{k}={v}" for k, v in ((f"java.io.{i}", f"java.io.{i}" * (i + 1)) for i in range(15))
        )
        long_headers = {f"key_{i}" * (i + 1): f"value_{i}" * (i + 1) for i in range(10)}
        long_headers["Referer"] = "javascript:alert('XSS');"
        long_headers["User-Agent"] = "Arachni/v1"
        self.r_waf_timeout = weblog.get(f"/waf/{long_payload}", headers=long_headers)

    @missing_feature(context.library < "java@0.113.0")
    @missing_feature("sinatra" in context.weblog_variant, reason="Sinatra endpoint not implemented")
    @dynamic_scenario(mandatory={"DD_APPSEC_WAF_TIMEOUT": "1"})
    def test_waf_timeout(self):
        """Test DD_APPSEC_WAF_TIMEOUT = low value"""
        assert self.r_waf_timeout.status_code == 200
        interfaces.library.assert_no_appsec_event(self.r_waf_timeout)

    def setup_obfuscation_parameter_key(self):
        self.r_op_key = weblog.get("/waf", headers={"hide-key": f"acunetix-user-agreement {self.SECRET}"})

    @missing_feature(context.library <= "ruby@1.0.0")
    @missing_feature(context.library < f"python@{PYTHON_RELEASE_GA_1_1}")
    @dynamic_scenario(
        mandatory={
            "DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP": "hide-key",
            "DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP": ".*hide_value",
        }
    )
    def test_obfuscation_parameter_key(self):
        """Test DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP"""

        def validate_appsec_span_tags(span, appsec_data):  # noqa: ARG001
            assert not nested_lookup(
                self.SECRET, appsec_data, look_in_keys=True
            ), "The security events contain the secret value that should be obfuscated"

        interfaces.library.assert_waf_attack(self.r_op_key, pattern="<Redacted>")
        interfaces.library.validate_appsec(self.r_op_key, validate_appsec_span_tags, success_by_default=True)

    def setup_obfuscation_parameter_value(self):
        headers = {"attack": f"acunetix-user-agreement {self.SECRET_WITH_HIDDEN_VALUE}"}
        self.r_op_value = weblog.get("/waf", headers=headers)

    @missing_feature(context.library <= "ruby@1.0.0")
    @missing_feature(context.library < f"python@{PYTHON_RELEASE_GA_1_1}")
    @dynamic_scenario(
        mandatory={
            "DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP": "hide-key",
            "DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP": ".*hide_value",
        }
    )
    def test_obfuscation_parameter_value(self):
        """Test DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP"""

        def validate_appsec_span_tags(span, appsec_data):  # noqa: ARG001
            assert not nested_lookup(
                self.SECRET_WITH_HIDDEN_VALUE, appsec_data, look_in_keys=True
            ), "The security events contain the secret value that should be obfuscated"

        interfaces.library.assert_waf_attack(self.r_op_value, pattern="<Redacted>")
        interfaces.library.validate_appsec(self.r_op_value, validate_appsec_span_tags, success_by_default=True)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2355333252/Environment+Variables")
@features.threats_configuration
@dynamic_scenario(mandatory={"DD_APPSEC_RULES": "/appsec_blocking_rule.json"})
class Test_ConfigurationVariables_New_Obfuscation:
    """Check for new obfuscation features in libddwaf 1.25.0 and later
    Requires libddwaf 1.25.0 or later and updated obfuscation regex for values
    """

    SECRET_WITH_HIDDEN_VALUE = "hide_value"

    def setup_partial_obfuscation_parameter_value(self):
        self.r_op_value = weblog.get(f"/.git?password={self.SECRET_WITH_HIDDEN_VALUE}")

    @missing_feature(context.library <= "ruby@1.0.0")
    def test_partial_obfuscation_parameter_value(self):
        """Test DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP"""

        def validate_appsec_span_tags(span, appsec_data):  # noqa: ARG001
            assert not nested_lookup(
                self.SECRET_WITH_HIDDEN_VALUE, appsec_data, look_in_keys=True
            ), "The security events contain the secret value that should be obfuscated"

        # previously, the value was obfuscated as "<Redacted>", now only the secret part is obfuscated
        interfaces.library.assert_waf_attack(self.r_op_value, value="/.git?password=<Redacted>")
        interfaces.library.validate_appsec(self.r_op_value, validate_appsec_span_tags, success_by_default=True)
