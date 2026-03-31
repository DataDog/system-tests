# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Concrete test classes for appsec_apm_standalone smoke tests."""

from utils import features, scenarios

from tests.appsec.test_agent_level_smoke_tests import (
    ApiSecuritySmokeTests,
    RaspSmokeTests,
    RemoteConfigSmokeTests,
    TelemetrySmokeTests,
    ThreatsSmokeTests,
    UserEventsSmokeTests,
)


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_Threats(ThreatsSmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_Rasp(RaspSmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_Telemetry(TelemetrySmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_RemoteConfig(RemoteConfigSmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_ApiSecurity(ApiSecuritySmokeTests):
    pass


@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecAPMStandalone_UserEvents(UserEventsSmokeTests):
    pass
