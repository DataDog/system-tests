# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, irrelevant

# *ATTENTION*: Copy this file to the tests folder, modify, and rename with a prefix of `test_` to enable your new tests

# There are ways to mark a test to be skipped in pytest, which may or may not be relevant for your tests.
# Use any of the following examples and add them as decorators on your test class.
#  - Require a specific version condition:
#       @bug(context.library < "golang@1.36.0")
#  - Skip for an entire library:
#       @irrelevant(context.library != "java", reason="*ATTENTION*: The reason the language is skipped")
#  - Skip for every library except one
#       @irrelevant(context.library = "dotnet", reason="only for .NET")

# To run an individual test: ./run.sh tests/test_traces.py::Test_Misc::test_main
class Test_Misc(BaseTestCase):
    """ *ATTENTION*: This is where you summarize the test """

    def test_main(self):
        # This is where you make your requests and assertions
        request = self.weblog_get("/trace/http")
        interfaces.library.assert_trace_exists(request, span_type="web")

        # You can make several requests and assertions to fulfill the needs of a test
        request = self.weblog_get("/trace/mongo")
        interfaces.library.assert_trace_exists(request, span_type="mongo")

        # The interfaces.library namespace is used to expose valuable assertions

        # If you want to create custom validations:
        #   - Follow the assert_trace_exists method down to examine how assertions and validations are structured.
        #   - Create your own assertions and methods for use in tests.
