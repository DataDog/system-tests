# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, rfc, irrelevant, missing_feature


@released(golang="1.34.0", java="0.90.0", python="?", ruby="?")
@irrelevant(context.library >= "golang@1.35.0", reason="appsec span tags")
@irrelevant(library="cpp")
class Test_Events(BaseTestCase):
    """AppSec events uses version 1.0 (legacy appsec events on dedicated entry point)"""

    @irrelevant(library="php", reason="reporting outside traces is not and will not be supported")
    @irrelevant(library="dotnet")
    @irrelevant(library="nodejs")
    def test_1_0(self):
        def validator(event):
            assert event["event_version"] == "1.0.0", f"event version should be 1.0.0, not {event['event_version']}"

            return True

        interfaces.library.add_appsec_validation(legacy_validator=validator)
