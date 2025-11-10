# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import (
    interfaces,
    scenarios,
    weblog,
    features,
)
from utils.dd_constants import Capabilities, SamplingPriority


@features.appsec_trace_tagging_rules
@scenarios.appsec_blocking
@scenarios.appsec_lambda_blocking
class Test_TraceTaggingRules:
    """Test different variants of trace-tagging rules"""

    def setup_rule_with_attributes_no_keep_no_event(self):
        self.r_tt1 = weblog.get("/waf/", headers={"User-Agent": "TraceTagging/v1"})

    def test_rule_with_attributes_no_keep_no_event(self):
        """Test trace-tagging rule with attributes, no keep and no event"""

        def validate(span: dict):
            if span.get("parent_id") not in (0, None):
                return None

            assert "_dd.appsec.trace.agent" in span["meta"], "Missing _dd.appsec.trace.agent from span's meta"
            assert "_dd.appsec.trace.integer" in span["metrics"], "Missing _dd.appsec.trace.integer from span's metrics"

            assert span["meta"]["_dd.appsec.trace.agent"].startswith("TraceTagging/v1")
            assert span["metrics"]["_dd.appsec.trace.integer"] == 662607015
            assert span["metrics"].get("_sampling_priority_v1") < SamplingPriority.USER_KEEP

            return True

        assert self.r_tt1.status_code == 200
        interfaces.library.validate_one_span(self.r_tt1, validator=validate)

    def setup_rule_with_attributes_keep_no_event(self):
        self.r_tt2 = weblog.get("/waf/", headers={"User-Agent": "TraceTagging/v2"})

    def test_rule_with_attributes_keep_no_event(self):
        """Test trace-tagging rule with attributes, sampling priority user_keep and no event"""

        def validate(span: dict):
            if span.get("parent_id") not in (0, None):
                return None

            assert "_dd.appsec.trace.agent" in span["meta"], "Missing _dd.appsec.trace.agent from span's meta"
            assert "_dd.appsec.trace.integer" in span["metrics"], "Missing _dd.appsec.trace.integer from span's metrics"

            assert span["meta"]["_dd.appsec.trace.agent"].startswith("TraceTagging/v2")
            assert span["metrics"]["_dd.appsec.trace.integer"] == 602214076
            assert span["metrics"].get("_sampling_priority_v1") == SamplingPriority.USER_KEEP

            return True

        assert self.r_tt2.status_code == 200
        interfaces.library.validate_one_span(self.r_tt2, validator=validate)

    def setup_rule_with_attributes_keep_event(self):
        self.r_tt3 = weblog.get("/waf/", headers={"User-Agent": "TraceTagging/v3"})

    def test_rule_with_attributes_keep_event(self):
        """Test trace-tagging rule with attributes, sampling priority user_keep and an event"""

        def validate(span: dict):
            if span.get("parent_id") not in (0, None):
                return None

            assert "_dd.appsec.trace.agent" in span["meta"], "Missing _dd.appsec.trace.agent from span's meta"
            assert "_dd.appsec.trace.integer" in span["metrics"], "Missing _dd.appsec.trace.integer from span's metrics"

            assert span["meta"]["_dd.appsec.trace.agent"].startswith("TraceTagging/v3")
            assert span["metrics"]["_dd.appsec.trace.integer"] == 299792458
            assert span["metrics"].get("_sampling_priority_v1") == SamplingPriority.USER_KEEP

            return True

        assert self.r_tt3.status_code == 200
        interfaces.library.assert_waf_attack(self.r_tt3, rule="ttr-000-003")
        interfaces.library.validate_one_span(self.r_tt3, validator=validate)

    def setup_rule_with_attributes_no_keep_event(self):
        self.r_tt4 = weblog.get("/waf/", headers={"User-Agent": "TraceTagging/v4"})

    def test_rule_with_attributes_no_keep_event(self):
        """Test trace-tagging rule with attributes and an event, but no sampling priority change"""

        def validate(span: dict):
            if span.get("parent_id") not in (0, None):
                return None

            assert "_dd.appsec.trace.agent" in span["meta"], "Missing _dd.appsec.trace.agent from span's meta"
            assert "_dd.appsec.trace.integer" in span["metrics"], "Missing _dd.appsec.trace.integer from span's metrics"

            assert span["meta"]["_dd.appsec.trace.agent"].startswith("TraceTagging/v4")
            assert span["metrics"]["_dd.appsec.trace.integer"] == 1729
            assert span["metrics"].get("_sampling_priority_v1") < SamplingPriority.USER_KEEP

            return True

        assert self.r_tt4.status_code == 200
        interfaces.library.assert_waf_attack(self.r_tt4, rule="ttr-000-004")
        interfaces.library.validate_one_span(self.r_tt4, validator=validate)


@scenarios.appsec_api_security_rc
@features.appsec_trace_tagging_rules
class Test_TraceTaggingRulesRcCapability:
    """A library with support for trace-tagging rules must provide the
    ASM_TRACE_TAGGING_RULES(43) capability
    """

    def test_trace_tagging_rules_capability(self):
        interfaces.library.assert_rc_capability(Capabilities.ASM_TRACE_TAGGING_RULES)
