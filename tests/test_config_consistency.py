# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features

# @scenarios.tracing_config_nondefault
@pytest.mark.parametrize("library_env", [{ "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": "" }])
class Test_Config_ObfuscationQueryStringRegexp_EmptyString:
    """ Verify behavior when set to empty string """
    with test_library as t:
        query_string = "application_key=123"
        resp = t.query_string_obfuscation(query_string)
    assert query_string in resp["http.url"] f""'{query_string}' not found in http.url"
    
# @scenarios.tracing_config_nondefault
@pytest.mark.parametrize("library_env", [{ "DD_TRACE_OBFUSCATION_QUERY_STRING_REGEXP": "ssn=\d{3}-\d{2}-\d{4}" }])
class Test_Config_ObfuscationQueryStringRegexp_Configured:
    """ Verify behavior when set to empty string """
    with test_library as t:
        query_string = "ssn=123-45-6789"
        resp = t.query_string_obfuscation(query_string)
    url = resp["http.url"]
    assert query_string not in url f""'{query_string}' unexpectedly found in http.url"
    assert "<redacted>" in url f""'<redacted>' not found in http.url"
    
