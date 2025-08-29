# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, features, interfaces, irrelevant, scenarios, flaky


@scenarios.appsec_blocking
@scenarios.appsec_lambda_blocking
@scenarios.appsec_rasp
@scenarios.appsec_runtime_activation
@scenarios.appsec_standalone
@scenarios.default
@scenarios.appsec_lambda_default
@features.language_specifics
@irrelevant(context.library not in ("python", "python_lambda"), reason="specific tests for python tracer")
class Test_ImportError:
    """Tests to verify that we don't have import errors due to tracer instrumentation."""

    @flaky(context.library == "python@3.2.1" and "flask" in context.weblog_variant, reason="APMRP-360")
    def test_circular_import(self):
        """Test to verify that we don't have a circular import in the weblog."""
        assert context.library in ("python", "python_lambda")
        interfaces.library_stdout.assert_absence("most likely due to a circular import")
