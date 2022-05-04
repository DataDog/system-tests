# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from utils import coverage, context, released


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@coverage.not_testable
class Test_MostCommonFramworkSupport:
    """ Detect attacks on the most common frameworks """


@coverage.not_testable
class Test_AppSecInMaster:
    """ AppSec code is merged into master/main branches """


@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_PerformanceControl:
    """ Performance controls (WAF time spent < 20ms) """

    # Is that necessary as we have a 5ms per callback?


@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_Telemetry:
    """ Telemetry """


@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", python="?")
class Test_Blocking:
    """ Blocking """


@coverage.not_implemented
@released(dotnet="?", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_AppsecWithoutApm:
    """ AppSec without APM """


@coverage.not_implemented
@released(dotnet="?", golang="?", nodejs="?", php_appsec="?", python="?", ruby="?")
class Test_BodyContentCollection:
    """ Request body content collection"""

    # probably not the good place
