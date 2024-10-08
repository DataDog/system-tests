# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, features, scenarios


#If your test verifies a feature, make sure you represent it
# @features.unix_domain_sockets_support_for_traces
@features.not_reported # This hides your feature from the jaws of the Feature Parity Dashboard
@scenarios.my_nice_scenario # Do you need this? Maybe? Only you can decide.
class Test_Demo:
    """ This is a place to describe the purpose of the test """

    def setup_very_nice_system_test_has_web_span(self):
        self.r = weblog.get("/my-cool-variable")

    def test_very_nice_system_test_has_web_span(self):
        # You can define multiple tests, but make sure they each have a setup :)
        interfaces.library.assert_trace_exists(self.r, span_type="web")

    def setup_very_nice_system_test_has_cool_tag_on_span(self):
        self.r = weblog.get("/my-cool-variable")
        
    def test_very_nice_system_test_has_cool_tag_on_span(self):
        span_count = 0
        for _, _, span in interfaces.library.get_spans(request=self.r):
            print(" !Span inspection! ")
            print(span)
            span_count += 1

        if span_count > 1:
            raise ValueError(f"Oh no, this endpoint should only have one span.")

        cool_tag = span["meta"]["DD_WOW_WOW"]
        cool_tag_expectation = "wow wow wee wow"
        if cool_tag != cool_tag_expectation:
            raise ValueError(f"Expected {cool_tag_expectation} but got {cool_tag}")
