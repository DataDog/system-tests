# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import interfaces, weblog, features, context

# Test_HardcodedSecretsExtended doesn't inherit from BaseSinkTest
# Hardcode secrets detection implementation change a lot between different languages
# current BaseSinkTest implementation doesn't work for all languages
# as the vulnerability is not always set in the current request span.


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
        hardcoded_secrets = self.get_hardcoded_secret_vulnerabilities()
        hardcoded_secrets = [v for v in hardcoded_secrets if v["evidence"]["value"] == "datadog-access-token"]
        assert len(hardcoded_secrets) == 1
        vuln = hardcoded_secrets[0]
        assert vuln["location"]["path"] == self._get_expectation(self.location_map)

    def get_hardcoded_secret_vulnerabilities(self):
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

    def _get_expectation(self, d):
        expected = d.get(context.library.library)
        if isinstance(expected, dict):
            expected = expected.get(context.weblog_variant)
        return expected
