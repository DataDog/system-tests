# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Concrete test classes for appsec_apm_standalone smoke tests."""

from utils import features, scenarios

from tests.appsec.smoke_tests.utils import (
    BaseApiSecuritySmokeTests,
    BaseRaspSmokeTests,
    BaseRemoteConfigSmokeTests,
    BaseTelemetrySmokeTests,
    BaseThreatsSmokeTests,
    BaseUserEventsSmokeTests,
)


# ── Class order matters ──────────────────────────────────────────────────────
# ApiSecurity must come BEFORE RemoteConfig: RC operations permanently disable
# API-security schema generation for the rest of the run.  ApiSecurity is
# marked flaky in the Java manifest and may be skipped; the WAF/RASP warmup
# therefore lives in Threats.setup_attack_detection_smoke (always runs).
# ─────────────────────────────────────────────────────────────────────────────


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_ApiSecurity(BaseApiSecuritySmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_Threats(BaseThreatsSmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_Rasp(BaseRaspSmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_Telemetry(BaseTelemetrySmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_RemoteConfig(BaseRemoteConfigSmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_UserEvents(BaseUserEventsSmokeTests):
    pass
