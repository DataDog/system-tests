# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Spike tests: validate that AppSec data survives the OTLP export path (M2 topology).

Scenario: APPSEC_OTEL_COLLECTOR
  - DD Tracer with AppSec enabled + blocking rules
  - Traces exported via OTLP (port 8127) → proxy → DD agent
  - RC via DD Agent (port 8126) with rc_api_enabled=True
  - include_opentelemetry=True + include_agent=True

Tests:
  1. WAF blocking (403) works with OTLP export
  2. AppSec event data in OTLP span attributes
  3. WAF trigger data in OTLP spans
  4. RC polling works via DD agent
  5. OTLP spans exist for attack requests
"""

import base64
import json
import re

from utils import weblog, interfaces, scenarios, features


def _find_appsec_keys_in_otlp():
    """Search all OTLP trace data for appsec-related attribute keys."""
    appsec_keys = set()
    for data in interfaces.open_telemetry.get_data(path_filters=["/v1/traces", "/api/v0.2/traces"]):
        content = data.get("request", {}).get("content", {})
        text = json.dumps(content)
        for m in re.finditer(r'"([^"]*appsec[^"]*)"\s*:', text, re.IGNORECASE):
            appsec_keys.add(m.group(1))
    return appsec_keys


def _find_waf_trigger_in_otlp():
    """Search OTLP trace data for WAF trigger data (rule ua0-600-12x for Arachni)."""
    for data in interfaces.open_telemetry.get_data(path_filters=["/v1/traces", "/api/v0.2/traces"]):
        content = data.get("request", {}).get("content", {})
        text = json.dumps(content)

        if "ua0-600" in text:
            return True

        for m in re.finditer(r'"appsec"\s*:\s*"([^"]+)"', text):
            encoded = m.group(1)
            try:
                decoded = base64.b64decode(encoded).decode("utf-8", errors="replace")
                if "ua0-600" in decoded or "trigger" in decoded.lower():
                    return True
            except Exception:
                pass
    return False


@features.not_reported
@scenarios.appsec_otlp_export
class Test_AppSec_OTLP_Blocking:
    """Verify WAF blocking works when traces are exported via OTLP."""

    def setup_waf_blocking(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_waf_blocking(self):
        """WAF blocking (403) should work — it happens in-tracer before any data export."""
        assert self.r.status_code == 403, (
            f"Expected 403 from WAF blocking, got {self.r.status_code}. "
            "Blocking happens in-tracer before any data export, so it should work with OTLP."
        )


@features.not_reported
@scenarios.appsec_otlp_export
class Test_AppSec_OTLP_Detection:
    """Verify AppSec detection data appears in OTLP spans."""

    def setup_appsec_event_in_otlp_spans(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_appsec_event_in_otlp_spans(self):
        """AppSec event data should appear in OTLP span attributes."""
        appsec_keys = _find_appsec_keys_in_otlp()

        assert len(appsec_keys) > 0, (
            "No AppSec data found in OTLP span attributes. "
            "This means dd-trace may not export AppSec data via OTLP."
        )
        assert "appsec.event" in appsec_keys, f"Missing 'appsec.event' key. Found: {appsec_keys}"
        assert "_dd.appsec.enabled" in appsec_keys, f"Missing '_dd.appsec.enabled' key. Found: {appsec_keys}"

    def setup_waf_trigger_data_in_otlp(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_waf_trigger_data_in_otlp(self):
        """WAF trigger data should be present in the appsec attribute of OTLP spans."""
        assert _find_waf_trigger_in_otlp(), (
            "WAF trigger data not found in OTLP spans. "
            "The 'appsec' attribute should contain encoded trigger data including rule ua0-600-12x."
        )


@features.not_reported
@scenarios.appsec_otlp_export
class Test_AppSec_OTLP_Structure:
    """Verify the structure of OTLP spans when AppSec is enabled."""

    def setup_otlp_spans_exist_for_attack(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_otlp_spans_exist_for_attack(self):
        """Sanity check: OTLP spans should exist for the attack request."""
        spans = list(interfaces.open_telemetry.get_otel_spans(self.r))
        assert len(spans) > 0, "No OTLP spans found for the attack request."

    def setup_appsec_attribute_keys(self):
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_appsec_attribute_keys(self):
        """Document all _dd.appsec.* attribute keys found in OTLP spans."""
        appsec_keys = _find_appsec_keys_in_otlp()

        print(f"\n=== AppSec attribute keys found in OTLP spans ===")
        for k in sorted(appsec_keys):
            print(f"  {k}")

        assert len(appsec_keys) > 0, "No _dd.appsec.* keys found in OTLP spans"
        assert "_dd.appsec.enabled" in appsec_keys
        assert "_dd.appsec.waf.version" in appsec_keys
        assert "_dd.appsec.event_rules.version" in appsec_keys


@features.not_reported
@scenarios.appsec_otlp_export
class Test_AppSec_OTLP_RCPolling:
    """Verify that Remote Config polling works when traces go via OTLP."""

    def test_rc_polling_in_library_interface(self):
        """RC polling traffic should appear in interfaces.library (tracer→agent on port 8126).

        With rc_api_enabled=True, the proxy adds /v0.7/config to the agent's /info endpoints,
        which tells the tracer that RC is available. The tracer should then poll /v0.7/config.
        """
        rc_paths = ["/v0.7/config", "/v0.7/config/"]
        found_rc = False

        for data in interfaces.library.get_data(path_filters=rc_paths):
            found_rc = True
            break

        # Document all paths found in library interface
        all_paths = set()
        for data in interfaces.library.get_data():
            all_paths.add(data.get("path", ""))

        print(f"\n=== All paths in library interface ===")
        for p in sorted(all_paths):
            print(f"  {p}")

        assert found_rc, (
            "No Remote Config polling traffic found in interfaces.library. "
            f"Paths found: {all_paths}. "
            "rc_api_enabled=True should add /v0.7/config to agent endpoints."
        )
