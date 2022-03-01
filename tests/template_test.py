# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, irrelevant
from utils.warmups import default_warmup

# This warmup task runs to make sure containers are ready to receive requests
context.add_warmup(default_warmup)

# *ATTENTION*: Copy this file, modify, and rename with a prefix of `test_` to enable your new tests

# There are ways to mark a test to be skipped in pytest, which may or may not be relevant for your tests
@irrelevant(context.library != "*ATTENTION*: language-to-skip", reason="*ATTENTION*: The reason the language is skipped")
class Test_Misc(BaseTestCase):
    """ *ATTENTION*: This is where you describe the summary of the test """

    def test_main(self):
        # This is where you make your requests and assertions
        r = self.weblog_get("/trace/http")
        interfaces.library.assert_trace_exists(r)

        # You can make several requests and assertions to fulfill the needs of a test
        r = self.weblog_get("/trace/mongo")
        interfaces.library.assert_trace_exists(r)

        # The interfaces.library namespace is used to expose valuable assertions

