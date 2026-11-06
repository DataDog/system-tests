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
from utils._decorators import rfc

apm_standalone_rfc = rfc(
    "https://datadoghq.atlassian.net/wiki/spaces/agent/pages/6319080743/APM+Standalone+Mode+Mode+Spec"
)

# --- APPSEC_APM_STANDALONE (DD_APM_TRACING_ENABLED=true) ---------------------


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
class Test_AppSecAPMStandalone_Threats(BaseThreatsSmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
class Test_AppSecAPMStandalone_Rasp(BaseRaspSmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
class Test_AppSecAPMStandalone_Telemetry(BaseTelemetrySmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
class Test_AppSecAPMStandalone_RemoteConfig(BaseRemoteConfigSmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
class Test_AppSecAPMStandalone_ApiSecurity(BaseApiSecuritySmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_apm_standalone
class Test_AppSecAPMStandalone_UserEvents(BaseUserEventsSmokeTests):
    pass


# --- APPSEC_STANDALONE_APM_STANDALONE (DD_APM_TRACING_ENABLED=false) ---------


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecStandaloneAPMStandalone_Threats(BaseThreatsSmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecStandaloneAPMStandalone_Rasp(BaseRaspSmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecStandaloneAPMStandalone_Telemetry(BaseTelemetrySmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecStandaloneAPMStandalone_RemoteConfig(BaseRemoteConfigSmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecStandaloneAPMStandalone_ApiSecurity(BaseApiSecuritySmokeTests):
    pass


@apm_standalone_rfc
@features.appsec_apm_standalone
@scenarios.appsec_standalone_apm_standalone
class Test_AppSecStandaloneAPMStandalone_UserEvents(BaseUserEventsSmokeTests):
    pass
