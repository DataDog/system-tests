# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Concrete test classes for APPSEC_OTLP_EXPORT smoke tests.

These smoke tests validate the same AppSec capabilities as the APM standalone
smoke tests, but with traces exported via OTLP instead of the Datadog agent
protocol.

Currently includes Threats and UserEvents smoke tests. RASP, RemoteConfig,
and ApiSecurity smoke tests require additional scenario configuration
(RASP ruleset, RC backend, API security enabled) not yet available in the
OTLP export scenarios.
"""

import pytest

from utils import features, scenarios, context

from tests.appsec.smoke_tests.utils import (
    BaseThreatsSmokeTests,
    BaseUserEventsSmokeTests,
)


pytestmark = pytest.mark.skipif(
    context.library not in ("python", "java"),
    reason="OTLP export is only configured for Python and Java",
)


# --- APPSEC_OTLP_EXPORT (blocking rules) ------------------------------------


@features.not_reported
@scenarios.appsec_otlp_export
class Test_AppSecOtlpExport_Threats(BaseThreatsSmokeTests):
    pass


@features.not_reported
@scenarios.appsec_otlp_export
class Test_AppSecOtlpExport_UserEvents(BaseUserEventsSmokeTests):
    pass


# --- APPSEC_OTLP_EXPORT_DEFAULT_RULES (default ruleset) --------------------


@features.not_reported
@scenarios.appsec_otlp_export_default_rules
class Test_AppSecOtlpExportDefaultRules_Threats(BaseThreatsSmokeTests):
    pass


@features.not_reported
@scenarios.appsec_otlp_export_default_rules
class Test_AppSecOtlpExportDefaultRules_UserEvents(BaseUserEventsSmokeTests):
    pass
