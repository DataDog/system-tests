# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import re
from urllib.parse import urlparse, parse_qs

from utils import scenarios, weblog, rfc, features, interfaces


def is_valid_uuid4(uuid_string):
    """Validate UUID format: 8-4-4-4-12 hex digits"""
    if not uuid_string or not isinstance(uuid_string, str):
        return False

    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
    return bool(uuid_pattern.match(uuid_string))


def extract_security_response_id_from_json(response_body):
    """Extract security_response_id from JSON blocking response

    RFC-1070: Libraries emit security_response_id in blocking responses
    Structure: {"errors": [...], "security_response_id": "uuid"}
    """
    try:
        data = json.loads(response_body)
        return data.get("security_response_id")
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return None


def extract_security_response_id_from_html(response_body):
    """Extract security_response_id from HTML blocking response

    RFC-1070: Libraries emit security_response_id in blocking responses
    Expected format: <p class="security-response-id">Security Response ID: {uuid}</p>
    """
    if not response_body:
        return None

    security_response_id_pattern = re.compile(
        r'<p\s+class=["\']security-response-id["\']\s*>Security\s+Response\s+ID:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})</p>',
        re.IGNORECASE,
    )
    match = security_response_id_pattern.search(response_body)
    if match:
        return match.group(1)

    return None


def extract_security_response_id_from_redirect_url(location_url):
    """Extract security_response_id from custom redirect URL query parameters

    RFC-1070: Libraries emit security_response_id in blocking responses
    Expected format: http://example.com/redirect?security_response_id={uuid}
    """
    if not location_url:
        return None

    try:
        parsed_url = urlparse(location_url)
        query_params = parse_qs(parsed_url.query)
        security_response_id_list = query_params.get("security_response_id", [])
        if security_response_id_list:
            return security_response_id_list[0]
        return None
    except Exception:
        return None


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/4235215165/RFC-1070+Blocking+Response+Unique+Identifier")
@features.blocking_response_id
@scenarios.appsec_blocking
class Test_SecurityResponseId_JSON_Response:
    """Test that security_response_id is present in JSON blocking responses"""

    def setup_security_response_id_in_json_response(self):
        """Trigger a blocking request with JSON response"""
        self.r_json = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})

    def test_security_response_id_in_json_response(self):
        """Verify security_response_id is present in JSON response and is a valid UUIDv4"""
        assert self.r_json.status_code == 403, f"Expected 403, got {self.r_json.status_code}"

        # Extract security_response_id from response
        security_response_id = extract_security_response_id_from_json(self.r_json.text)
        assert security_response_id is not None, f"security_response_id not found in JSON response: {self.r_json.text}"

        # Validate UUID format
        assert is_valid_uuid4(
            security_response_id
        ), f"security_response_id is not a valid UUIDv4: {security_response_id}"

    def setup_security_response_id_uniqueness(self):
        """Make multiple blocking requests to test uniqueness"""
        self.r1 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})
        self.r2 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})
        self.r3 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})

    def test_security_response_id_uniqueness(self):
        """Verify each blocking request gets a unique security_response_id"""
        assert self.r1.status_code == 403
        assert self.r2.status_code == 403
        assert self.r3.status_code == 403

        security_response_id_1 = extract_security_response_id_from_json(self.r1.text)
        security_response_id_2 = extract_security_response_id_from_json(self.r2.text)
        security_response_id_3 = extract_security_response_id_from_json(self.r3.text)

        assert security_response_id_1 is not None, "security_response_id not found in first response"
        assert security_response_id_2 is not None, "security_response_id not found in second response"
        assert security_response_id_3 is not None, "security_response_id not found in third response"

        # All security_response_ids should be unique
        assert (
            security_response_id_1 != security_response_id_2
        ), f"security_response_ids are not unique: {security_response_id_1} == {security_response_id_2}"
        assert (
            security_response_id_1 != security_response_id_3
        ), f"security_response_ids are not unique: {security_response_id_1} == {security_response_id_3}"
        assert (
            security_response_id_2 != security_response_id_3
        ), f"security_response_ids are not unique: {security_response_id_2} == {security_response_id_3}"


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/4235215165/RFC-1070+Blocking+Response+Unique+Identifier")
@features.blocking_response_id
@scenarios.appsec_blocking
class Test_SecurityResponseId_HTML_Response:
    """Test that security_response_id is present in HTML blocking responses"""

    def setup_security_response_id_in_html_response(self):
        """Trigger a blocking request with HTML response"""
        self.r_html = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/html"})

    def test_security_response_id_in_html_response(self):
        """Verify security_response_id is present in HTML response and is a valid UUIDv4"""
        assert self.r_html.status_code == 403, f"Expected 403, got {self.r_html.status_code}"

        # Extract security_response_id from HTML response
        security_response_id = extract_security_response_id_from_html(self.r_html.text)
        assert security_response_id is not None, f"security_response_id not found in HTML response: {self.r_html.text}"

        # Validate UUID format
        assert is_valid_uuid4(
            security_response_id
        ), f"security_response_id is not a valid UUIDv4: {security_response_id}"


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/4235215165/RFC-1070+Blocking+Response+Unique+Identifier")
@features.blocking_response_id
@scenarios.appsec_blocking
class Test_SecurityResponseId_Custom_Redirect:
    """Test that security_response_id can optionally be present in custom redirect URLs

    Note: This is an optional feature in RFC-1070. Tracers that implement
    custom redirect blocking actions CAN include the security_response_id as a query parameter.
    """

    def setup_security_response_id_in_redirect_url(self):
        """Trigger a blocking request that should redirect with security_response_id"""
        # Request with custom redirect blocking action that includes security_response_id in URL
        self.r_redirect = weblog.get("/waf/", headers={"User-Agent": "Canary/v5"}, allow_redirects=False)

    def test_security_response_id_in_redirect_url(self):
        """Verify security_response_id is present in redirect URL and is a valid UUIDv4"""
        assert self.r_redirect.status_code == 301, f"Expected 301, got {self.r_redirect.status_code}"

        # Extract Location header
        location = self.r_redirect.headers.get("Location")
        assert location is not None, "Redirect response missing Location header"

        # Extract security_response_id from URL query parameters
        security_response_id = extract_security_response_id_from_redirect_url(location)
        assert security_response_id is not None, f"security_response_id not found in redirect URL: {location}"

        # Validate UUID format
        assert is_valid_uuid4(
            security_response_id
        ), f"security_response_id is not a valid UUIDv4: {security_response_id}"


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/4235215165/RFC-1070+Blocking+Response+Unique+Identifier")
@features.blocking_response_id
@scenarios.appsec_blocking
class Test_SecurityResponseId_In_Span_Triggers:
    """Test that security_response_id is present in AppSec span triggers during blocking events

    RFC-1070: The WAF provides security_response_id to tracers, which emit it in
    the triggers array of the AppSec span data (_dd.appsec.json).
    """

    def setup_security_response_id_in_span_trigger(self):
        """Trigger a blocking request to validate security_response_id in span"""
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})

    def test_security_response_id_in_span_trigger(self):
        """Verify security_response_id is present in span trigger and is a valid UUIDv4"""
        assert self.r.status_code == 403, f"Expected 403, got {self.r.status_code}"

        # Get the root span and extract appsec data
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        meta_struct = span.get("meta_struct", {})

        # Extract appsec data (support both formats: meta_struct.appsec or meta._dd.appsec.json)
        appsec = meta.get("_dd.appsec.json", {}) or meta_struct.get("appsec", {})
        assert appsec, "No appsec data found in span"

        # Validate triggers structure exists
        triggers = appsec.get("triggers", [])
        assert len(triggers) > 0, "No triggers found in appsec data"

        # Extract security_response_id from first trigger
        trigger = triggers[0]
        security_response_id = trigger.get("security_response_id")
        assert security_response_id is not None, f"security_response_id not found in trigger: {trigger}"

        # Validate UUID format
        assert is_valid_uuid4(
            security_response_id
        ), f"security_response_id is not a valid UUIDv4: {security_response_id}"
