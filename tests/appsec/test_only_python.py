# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, interfaces, irrelevant, scenarios


@scenarios.appsec_api_security
@scenarios.appsec_api_security_rc
@scenarios.appsec_blocking
@scenarios.appsec_corrupted_rules
@scenarios.appsec_custom_rules
@scenarios.appsec_low_waf_timeout
@scenarios.appsec_missing_rules
@scenarios.appsec_rate_limiter
@scenarios.appsec_rasp
@scenarios.appsec_runtime_activation
@scenarios.appsec_standalone
@scenarios.default
@irrelevant(context.library != "python", reason="specific tests for python tracer")
class Test_ImportError:
    """Tests to verify that we don't have import errors due to tracer instrumentation."""

    def setup_circular_import(self):
        pass

    def test_circular_import(self):
        """Test to verify that we don't have a circular import in the weblog."""
        assert context.library == "python"
        interfaces.library_stdout.assert_absence("most likely due to a circular import")
