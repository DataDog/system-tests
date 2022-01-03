# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, rfc, irrelevant, missing_feature


@released(golang="1.35.0", java="0.90.0", nodejs="2.0.0rc0", python="?", ruby="?")
@irrelevant(library="cpp")
class Test_Events(BaseTestCase):
    """AppSec events uses version 1.0 (legacy appsec events on dedicated entry point)"""

    @irrelevant(context.library != "golang")
    def test_0_1(self):
        """ Check sends event using legacy /appsec/proxy/api/v2/appsecevts 0.1.0"""

        def validator(event):
            assert event["event_version"] == "1.0.0", f"event version should be 0.1.0, not {event['event_version']}"

            return True

        def new_validator(span, event):
            raise Exception("You are using AppSec in traces, you can skip this test")

        interfaces.library.add_appsec_validation(legacy_validator=validator, validator=new_validator)

    @irrelevant(library="golang")
    @irrelevant(library="php")
    @irrelevant(library="dotnet")
    @irrelevant(library="nodejs")
    @irrelevant(context.library >= "java@0.93.0")
    def test_1_0(self):
        """ Check sends event using legacy /appsec/proxy/api/v2/appsecevts 1.0.0"""

        def validator(event):
            assert event["event_version"] == "1.0.0", f"event version should be 1.0.0, not {event['event_version']}"

            return True

        def new_validator(span, event):
            raise Exception("You are using AppSec in traces, you can skip this test")

        interfaces.library.add_appsec_validation(legacy_validator=validator, validator=new_validator)

    @missing_feature(library="golang")
    @missing_feature(context.library < "java@0.93.0")
    def test_appsec_in_traces(self):
        """ AppSec sends event in traces"""

        def validator(event):
            raise Exception("You are using old AppSec communication")

        def new_validator(span, event):
            return True

        interfaces.library.add_appsec_validation(legacy_validator=validator, validator=new_validator)
