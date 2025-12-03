# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Tests for RUM (Real User Monitoring) support scenario"""

from html.parser import HTMLParser

from utils import weblog, features


@features.not_reported
class Test_RUM_Injection:
    """Basic tests to verify RUM injection is working"""

    def setup_rum_enabled(self):
        """Make a request to generate HTML with RUM configuration enabled"""
        self.response = weblog.get("/html")

    def test_rum_enabled(self):
        """Verify that RUM scripts are injected into the HTML response"""
        assert self.response.status_code == 200, f"Expected 200, got {self.response.status_code}"

        html = self.response.text

        # Validate HTML is well-formed
        assert _is_valid_html(html), "HTML is malformed"

        # Validate RUM SDK script is present (ignoring version number)
        assert "https://www.datadoghq-browser-agent.com/datadog-rum-v" in html, "RUM SDK script not found"

        # Validate RUM initialization call is present
        assert "window.DD_RUM.init" in html, "RUM init call not found"


def _is_valid_html(html: str) -> bool:
    """Check if HTML is well-formed"""
    try:
        HTMLParser().feed(html)
        return True
    except Exception:
        return False
