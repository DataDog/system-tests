# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import interfaces, weblog, features, context, rfc, weblog
from ..utils import validate_stack_traces

# Test_HardcodedSecrets and Test_HardcodedSecretsExtended don't inherit from BaseSinkTest
# Hardcode secrets detection implementation change a lot between different languages
# current BaseSinkTest implementation doesn't work for all languages
# as the vulnerability is not always set in the current request span.


def get_hardcoded_secret_vulnerabilities():
    spans = [s for _, s in interfaces.library.get_root_spans()]
    assert spans, "No spans found"
    spans_meta = [span.get("meta") for span in spans]
    assert spans_meta, "No spans meta found"
    iast_events = [meta.get("_dd.iast.json") for meta in spans_meta if meta.get("_dd.iast.json")]
    assert iast_events, "No iast events found"
    vulnerabilities = [event.get("vulnerabilities") for event in iast_events if event.get("vulnerabilities")]
    assert vulnerabilities, "No vulnerabilities found"
    vulnerabilities = sum(vulnerabilities, [])  # set all the vulnerabilities in a single list
    hardcoded_secrets = [vuln for vuln in vulnerabilities if vuln.get("type") == "HARDCODED_SECRET"]
    assert hardcoded_secrets, "No hardcoded secrets found"
    return hardcoded_secrets


def get_expectation(d):
    expected = d.get(context.library.library)
    if isinstance(expected, dict):
        expected = expected.get(context.weblog_variant)
    return expected


@features.iast_sink_hardcoded_secrets
class Test_HardcodedSecrets:
    """Test Hardcoded secrets detection."""

    location_map = {
        "java": "com.datadoghq.system_tests.springboot.AppSecIast",
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts", "uds-express4": "iast/index.js"},
    }

    insecure_request = None

    def setup_hardcoded_secrets_exec(self):
        self.r_hardcoded_secrets_exec = weblog.get("/iast/hardcoded_secrets/test_insecure")
        self.__class__.insecure_request = self.r_hardcoded_secrets_exec

    def test_hardcoded_secrets_exec(self):
        assert self.r_hardcoded_secrets_exec.status_code == 200
        hardcode_secrets = get_hardcoded_secret_vulnerabilities()
        hardcode_secrets = [v for v in hardcode_secrets if v["evidence"]["value"] == "aws-access-token"]
        assert len(hardcode_secrets) == 1
        vuln = hardcode_secrets[0]
        assert vuln["location"]["path"] == get_expectation(self.location_map)


@features.iast_sink_hardcoded_secrets
class Test_HardcodedSecretsExtended:
    """Test Hardcoded secrets extended detection."""

    location_map = {
        "nodejs": {"express4": "iast/index.js", "express4-typescript": "iast.ts", "uds-express4": "iast/index.js"},
    }

    def setup_hardcoded_secrets_extended_exec(self):
        self.r_hardcoded_secrets_exec = weblog.get("/iast/hardcoded_secrets_extended/test_insecure")

    def test_hardcoded_secrets_extended_exec(self):
        assert self.r_hardcoded_secrets_exec.status_code == 200
        hardcoded_secrets = get_hardcoded_secret_vulnerabilities()
        hardcoded_secrets = [v for v in hardcoded_secrets if v["evidence"]["value"] == "datadog-access-token"]
        assert len(hardcoded_secrets) == 1
        vuln = hardcoded_secrets[0]
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
