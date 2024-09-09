# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.
from utils import weblog, interfaces, scenarios, features

# Tests for verifying default query string obfuscation behavior can be found in the Test_StandardTagsUrl test class
@scenarios.tracing_config_empty
class Test_Config_ObfuscationQueryStringRegexp_Empty:
    def test_query_string_obfuscation_empty(self, library_env, test_library):
        """ Verify behavior when set to empty string """
        req = weblog.get("/waf?application_key=123" + query_string)
        interfaces.library.add_span_tag_validation(req, r"application_key=123", value_as_regular_expression=True,)
    
# @scenarios.tracing_config_nondefault
# # @pytest.mark.parametrize("library_env", [{ "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": "ssn=\d{3}-\d{2}-\d{4}" }])
# class Test_Config_ObfuscationQueryStringRegexp_Configured:
#     def test_query_string_obfuscation_configured(self, library_env, test_library):
#         """ Verify behavior when set to empty string """
#         with test_library as t:
#             query_string = "ssn=123-45-6789"
#             resp = t.query_string_obfuscation(query_string)
#         url = resp["http_url"]
#         assert query_string not in url, f"""'{query_string}' unexpectedly found in http.url"""
#         assert "<redacted>" in url, f"""'<redacted>' not found in http.url"""
    
