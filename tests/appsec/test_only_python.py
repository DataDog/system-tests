# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, features, interfaces, irrelevant, scenarios, flaky
from utils._context._scenarios.dynamic import dynamic_scenario



@dynamic_scenario(mandatory={"DD_APPSEC_RULES": "/appsec_blocking_rule.json"})
@dynamic_scenario(mandatory={"DD_APPSEC_RASP_ENABLED": "true", "DD_APPSEC_RULES": "/appsec_rasp_ruleset.json", "DD_APPSEC_RASP_COLLECT_REQUEST_BODY": "true"})
@dynamic_scenario(mandatory={"DD_APPSEC_WAF_TIMEOUT": "10000000", "DD_APPSEC_TRACE_RATE_LIMIT": "10000"})
@dynamic_scenario(mandatory={"DD_APPSEC_ENABLED": "true", "DD_APM_TRACING_ENABLED": "false", "DD_IAST_ENABLED": "false", "DD_API_SECURITY_ENABLED": "false", "DD_APPSEC_COLLECT_ALL_HEADERS": "true", "DD_APPSEC_HEADER_COLLECTION_REDACTION_ENABLED": "false", "DD_TRACE_STATS_COMPUTATION_ENABLED": "false"})
@scenarios.default
@features.language_specifics
@irrelevant(context.library != "python", reason="specific tests for python tracer")
class Test_ImportError:
    """Tests to verify that we don't have import errors due to tracer instrumentation."""

    @flaky(context.library == "python@3.2.1" and "flask" in context.weblog_variant, reason="APMRP-360")
    def test_circular_import(self):
        """Test to verify that we don't have a circular import in the weblog."""
        assert context.library == "python"
        interfaces.library_stdout.assert_absence("most likely due to a circular import")
