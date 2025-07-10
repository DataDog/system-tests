# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, features, context, rfc
from tests.appsec.iast.utils import get_hardcoded_vulnerabilities, validate_stack_traces, get_nodejs_iast_file_paths

# Test_HardcodedPasswords doesn't inherit from BaseSinkTest
# Hardcode passwords detection implementation change a lot between different languages
# current BaseSinkTest implementation doesn't work for all languages
# as the vulnerability is not always set in the current request span.


@features.iast_sink_hardcoded_passwords
class Test_HardcodedPasswords:
    """Test Hardcoded passwords detection."""

    location_map = {
        "nodejs": get_nodejs_iast_file_paths(),
    }

    insecure_request = None

    def setup_hardcoded_passwords_exec(self):
        self.r_hardcoded_passwords_exec = weblog.get("/iast/hardcoded_passwords/test_insecure")
        self.__class__.insecure_request = self.r_hardcoded_passwords_exec

    def test_hardcoded_passwords_exec(self):
        assert self.r_hardcoded_passwords_exec.status_code == 200
        hardcoded_passwords = get_hardcoded_vulnerabilities("HARDCODED_PASSWORD")
        hardcoded_passwords = [v for v in hardcoded_passwords if v["evidence"]["value"] == "hashpwd"]
        assert len(hardcoded_passwords) == 1
        vuln = hardcoded_passwords[0]
        assert vuln["location"]["path"] == self._get_expectation(self.location_map)

    def _get_expectation(self, d):
        expected = d.get(context.library.name)
        if isinstance(expected, dict):
            expected = expected.get(context.weblog_variant)
        return expected


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class Test_HardcodedPasswords_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/hardcoded_passwords/test_insecure")

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class Test_HardcodedPasswords_ExtendedLocation:
    """Test extended location data"""

    def setup_extended_location_data(self):
        self.r = weblog.get("/iast/hardcoded_passwords/test_insecure")

    def test_extended_location_data(self):
        hardcoded_passwords = get_hardcoded_vulnerabilities("HARDCODED_PASSWORD")
        hardcoded_passwords = [v for v in hardcoded_passwords if v["evidence"]["value"] == "hashpwd"]
        assert len(hardcoded_passwords) == 1
        location = hardcoded_passwords[0]["location"]

        assert all(field in location for field in ["path", "line"])

        if context.library.name not in ("python", "nodejs"):
            assert all(field in location for field in ["class", "method"])
