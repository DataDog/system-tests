# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.
from utils import weblog, interfaces, scenarios, features

# Tests for verifying default query string obfuscation behavior can be found in the Test_StandardTagsUrl test class
@scenarios.tracing_config_empty
class Test_Config_ObfuscationQueryStringRegexp_Empty:
    """ Verify behavior when set to empty string """
    def setup_query_string_obfuscation_empty(self):
        self.r = weblog.get("/some-endpoint?application_key=123")

    def test_query_string_obfuscation_empty(self):
        interfaces.library.add_span_tag_validation(self.r, tags={"http.url": r"^.*/some-endpoint\?application_key=123$"}, value_as_regular_expression=True,)
    
@scenarios.tracing_config_nondefault
class Test_Config_ObfuscationQueryStringRegexp_Configured:
    def setup_query_string_obfuscation_configured(self):
        self.r = weblog.get("/some-endpoint?ssn=123-45-6789")

    def test_query_string_obfuscation_empty(self):
        interfaces.library.add_span_tag_validation(self.r, tags={"http.url": r"^.*/some-endpoint\?application_key=<redacted>$"}, value_as_regular_expression=True,)
    
