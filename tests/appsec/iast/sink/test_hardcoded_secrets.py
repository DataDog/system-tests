# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, interfaces, weblog, features, context


@features.iast_sink_hardcoded_secrets
@coverage.basic
class Test_HardcodedSecrets:
    """Test Hardcoded secrets detection."""

    location_map = {"nodejs": "iast/index.js", "java": "com.datadoghq.system_tests.springboot.AppSecIast"}

    def setup_hardcoded_secrets_exec(self):
        self.r_hardcoded_secrets_exec = weblog.get("/iast/hardcoded_secrets/test_insecure")

    def test_hardcoded_secrets_exec(self):
        assert self.r_hardcoded_secrets_exec.status_code == 200
        hardcode_secrets = self.get_hardcoded_secret_vulnerabilities()
        evidence_condition = lambda x: x["evidence"]["value"] == "aws-access-token"
        location_condition = lambda x: x["location"]["path"] == self._get_expectation(self.location_map)
        assert any([evidence_condition(x) and location_condition(x) for x in hardcode_secrets]), (
            "Hardcoded secrets not found %s" % hardcode_secrets
        )

    def get_hardcoded_secret_vulnerabilities(self):
        spans = [span[2] for span in interfaces.library.get_spans()]
        assert spans, "No spans found"
        spans_meta = [span.get("meta") for span in spans]
        assert spans_meta, "No spans meta found"
        iast_events = [meta.get("_dd.iast.json") for meta in spans_meta if meta.get("_dd.iast.json")]
        assert iast_events, "No iast events found"
        vulnerabilities = [event.get("vulnerabilities") for event in iast_events if event.get("vulnerabilities")]
        assert vulnerabilities, "No vulnerabilities found"
        vulnerabilities = sum(vulnerabilities, [])  # set all the vulnerabilities in a single list
        hadcoded_secrets = [vuln for vuln in vulnerabilities if vuln.get("type") == "HARDCODED_SECRET"]
        assert hadcoded_secrets, "No hardcoded secrets found"
        return hadcoded_secrets

    def _get_expectation(self, d):
        if d is None or isinstance(d, str):
            return d

        if isinstance(d, dict):
            expected = d.get(context.library.library)
            if isinstance(expected, dict):
                expected = expected.get(context.weblog_variant)
            return expected

        raise TypeError(f"Unsupported expectation type: {d}")
