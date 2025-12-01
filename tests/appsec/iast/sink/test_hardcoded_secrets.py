# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, context, rfc, weblog
from tests.appsec.iast.utils import get_hardcoded_vulnerabilities, validate_stack_traces, get_nodejs_iast_file_paths

# Test_HardcodedSecrets and Test_HardcodedSecretsExtended don't inherit from BaseSinkTest
# Hardcode secrets detection implementation change a lot between different languages
# current BaseSinkTest implementation doesn't work for all languages
# as the vulnerability is not always set in the current request span.


def get_expectation(d: dict):
    expected = d.get(context.library.name)
    if isinstance(expected, dict):
        expected = expected.get(context.weblog_variant)
    return expected


@features.iast_sink_hardcoded_secrets
class Test_HardcodedSecrets:
    """Test Hardcoded secrets detection."""

    location_map = {
        "java": "com.datadoghq.system_tests.springboot.AppSecIast",
        "nodejs": get_nodejs_iast_file_paths(),
    }

    insecure_request = None

    def setup_hardcoded_secrets_exec(self):
        self.r_hardcoded_secrets_exec = weblog.get("/iast/hardcoded_secrets/test_insecure")
        self.__class__.insecure_request = self.r_hardcoded_secrets_exec

    def test_hardcoded_secrets_exec(self):
        assert self.r_hardcoded_secrets_exec.status_code == 200
        hardcode_secrets = get_hardcoded_vulnerabilities("HARDCODED_SECRET")
        hardcode_secrets = [v for v in hardcode_secrets if v["evidence"]["value"] == "aws-access-token"]
        # Deduplicate by hash in case the tracer reports the same secret multiple times
        unique_secrets = {v["hash"]: v for v in hardcode_secrets}.values()
        assert len(unique_secrets) == 1, f"Expected 1 unique secret, found {len(unique_secrets)}"
        vuln = list(unique_secrets)[0]
        assert vuln["location"]["path"] == get_expectation(self.location_map)


@features.iast_sink_hardcoded_secrets
class Test_HardcodedSecretsExtended:
    """Test Hardcoded secrets extended detection."""

    location_map = {
        "nodejs": get_nodejs_iast_file_paths(),
    }

    def setup_hardcoded_secrets_extended_exec(self):
        self.r_hardcoded_secrets_exec = weblog.get("/iast/hardcoded_secrets_extended/test_insecure")

    def test_hardcoded_secrets_extended_exec(self):
        assert self.r_hardcoded_secrets_exec.status_code == 200
        hardcoded_secrets = get_hardcoded_vulnerabilities("HARDCODED_SECRET")
        hardcoded_secrets = [v for v in hardcoded_secrets if v["evidence"]["value"] == "datadog-access-token"]
        # Deduplicate by hash in case the tracer reports the same secret multiple times
        unique_secrets = {v["hash"]: v for v in hardcoded_secrets}.values()
        assert len(unique_secrets) == 1, f"Expected 1 unique secret, found {len(unique_secrets)}"
        vuln = list(unique_secrets)[0]
        assert vuln["location"]["path"] == get_expectation(self.location_map)


@rfc(
    "https://docs.google.com/document/d/1ga7yCKq2htgcwgQsInYZKktV0hNlv4drY9XzSxT-o5U/edit?tab=t.0#heading=h.d0f5wzmlfhat"
)
@features.iast_stack_trace
class Test_HardcodedSecrets_StackTrace:
    """Validate stack trace generation"""

    def setup_stack_trace(self):
        self.r = weblog.get("/iast/hardcoded_secrets/test_insecure")

    def test_stack_trace(self):
        validate_stack_traces(self.r)


@rfc("https://docs.google.com/document/d/1R8AIuQ9_rMHBPdChCb5jRwPrg1WvIz96c_WQ3y8DWk4")
@features.iast_extended_location
class Test_HardcodedSecrets_ExtendedLocation:
    """Test extended location data"""

    def setup_extended_location_data(self):
        self.r = weblog.get("/iast/hardcoded_secrets/test_insecure")

    def test_extended_location_data(self):
        hardcode_secrets = get_hardcoded_vulnerabilities("HARDCODED_SECRET")
        hardcode_secrets = [v for v in hardcode_secrets if v["evidence"]["value"] == "aws-access-token"]
        # Deduplicate by hash in case the tracer reports the same secret multiple times
        unique_secrets = {v["hash"]: v for v in hardcode_secrets}.values()
        assert len(unique_secrets) == 1, f"Expected 1 unique secret, found {len(unique_secrets)}"
        location = list(unique_secrets)[0]["location"]

        assert all(field in location for field in ["path", "line"])

        if context.library.name not in ("python", "nodejs"):
            assert all(field in location for field in ["class", "method"])
