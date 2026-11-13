# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Security carrier validation with native tracing."""

from utils import features, scenarios
from tests.appsec.smoke_tests.utils import BaseThreatsSmokeTests


@features.security_events_metadata
@scenarios.security_smoke
class Test_SecuritySmoke_Threats(BaseThreatsSmokeTests):
    pass
