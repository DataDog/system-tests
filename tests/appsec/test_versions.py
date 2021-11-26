# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, rfc, irrelevant, missing_feature


@released(dotnet="?", golang="?", java="0.90.0", nodejs="2.0.0-appsec-alpha.1", python="?", ruby="?")
@missing_feature(library="php", reason="reporting outside traces is not and will not be supported")
@irrelevant(library="cpp")
class Test_Events(BaseTestCase):
    """AppSec events uses version 1.0 (legacy appsec events on dedicated entry point)"""

    def test_1_0(self):
        def validator(event):
            assert event["event_version"] == "1.0.0", f"event version should be 1.0.0, not {event['event_version']}"

            return True

        interfaces.library.add_appsec_validation(legacy_validator=validator)


@rfc("https://github.com/DataDog/appsec-event-rules/tree/1.0.0/v2/build")
@released(dotnet="1.30.0", golang="?", java="0.90.0")
@released(nodejs="2.0.0-appsec-alpha.1", php="0.1.0", python="?", ruby="0.53.0")
@irrelevant(library="cpp")
class Test_LatestWafRuleSet(BaseTestCase):
    """AppSec WAF uses latest recommended rule set"""

    def test_1_0_0(self):
        assert context.waf_rule_set == "1.0.0"
