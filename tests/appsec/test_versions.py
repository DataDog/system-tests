# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released
from utils._context.core import not_relevant


@released(dotnet="?", golang="?", java="?", nodejs="nodejs@2.0.0-appsec-alpha.1", php="?", python="?", ruby="?")
@not_relevant(library="cpp")
@not_relevant(context.weblog_variant == "echo-poc")
class Test_Events(BaseTestCase):
    def test_1_0(self):
        """AppSec events uses version 1.0"""

        def validator(event):
            assert event["event_version"] == "1.0.0", f"event version should be 1.0.0, not {event['event_version']}"

            return True

        interfaces.library.add_appsec_validation(validator=validator)
