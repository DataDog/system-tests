# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Concrete test classes for APPSEC_OTEL_API smoke tests.

M1 topology: DD Tracer as drop-in OTel SDK replacement.
Uses standard DD agent for transport (native protocol), OTel API backed by dd-tracer.
"""

from utils import features, scenarios, context

from tests.appsec.smoke_tests.utils import (
    BaseThreatsSmokeTests,
    BaseUserEventsSmokeTests,
)


@features.not_reported
@scenarios.appsec_otel_api
class Test_AppSecOtelApi_Threats(BaseThreatsSmokeTests):
    pass


@features.not_reported
@scenarios.appsec_otel_api
class Test_AppSecOtelApi_UserEvents(BaseUserEventsSmokeTests):
    pass


@features.not_reported
@scenarios.appsec_otel_api_default_rules
class Test_AppSecOtelApiDefaultRules_Threats(BaseThreatsSmokeTests):
    pass


@features.not_reported
@scenarios.appsec_otel_api_default_rules
class Test_AppSecOtelApiDefaultRules_UserEvents(BaseUserEventsSmokeTests):
    pass
