# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, rfc, irrelevant, missing_feature


@released(golang="1.36.0", java="0.90.0", nodejs="2.0.0rc0", python="?", ruby="?")
@irrelevant(library="cpp")
class Test_Events(BaseTestCase):
    """AppSec events uses version 1.0 (legacy appsec events on dedicated entry point)"""

    @missing_feature(context.library < "java@0.93.0")
    def test_appsec_in_traces(self):
        """ AppSec sends event in traces"""

        def validator(event):
            raise Exception("You are using old AppSec communication")

        def new_validator(span, event):
            return True

        interfaces.library.add_appsec_validation(legacy_validator=validator, validator=new_validator)
