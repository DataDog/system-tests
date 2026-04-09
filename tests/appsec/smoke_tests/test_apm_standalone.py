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
# ApiSecurity must be FIRST: its setup contains the warmup request that
# initialises WAF/RASP for all subsequent classes, and the Java tracer only
# produces API-security schemas on the first request to an endpoint.
# RemoteConfig must come AFTER ApiSecurity: RC operations permanently disable
# schema generation for the rest of the run.
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
