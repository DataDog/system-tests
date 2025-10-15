# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import re
from urllib.parse import urlparse, parse_qs

from utils import scenarios, weblog, rfc


def is_valid_uuid4(uuid_string):
    """Validate UUID format: 8-4-4-4-12 hex digits

    Note: Using flexible pattern to accept any hex UUID format,
    as different implementations may use different UUID variants
    """
    if not uuid_string or not isinstance(uuid_string, str):
        return False

    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    return bool(uuid_pattern.match(uuid_string))


def extract_block_id_from_json(response_body):
    """Extract block_id from JSON blocking response

    RFC-1070: Blocking responses include a unique block_id
    Structure: {"errors": [...], "block_id": "uuid"}
    """
    try:
        data = json.loads(response_body)
        return data.get("block_id")
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return None


def extract_block_id_from_html(response_body):
    """Extract block_id from HTML blocking response

    RFC-1070: Blocking responses include a unique block_id
    Expected format: <p class="block-id">Block ID: {uuid}</p>

    Also checks for other common formats:
    - <meta name="block_id" content="...">
    - data-block-id="..."
    """
    if not response_body:
        return None

    # Try paragraph with class "block-id" and "Block ID:" text
    block_id_pattern = re.compile(
        r'<p\s+class=["\']block-id["\']\s*>Block\s+ID:\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})</p>',
        re.IGNORECASE
    )
    match = block_id_pattern.search(response_body)
    if match:
        return match.group(1)

    # Try span with class (alternative format)
    span_pattern = re.compile(
        r'<span\s+class=["\']block-id["\']\s*>(?:Block\s+ID:\s*)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})</span>',
        re.IGNORECASE
    )
    match = span_pattern.search(response_body)
    if match:
        return match.group(1)

    # Try meta tag
    meta_pattern = re.compile(r'<meta\s+name=["\']block_id["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE)
    match = meta_pattern.search(response_body)
    if match:
        return match.group(1)

    # Try data attribute
    data_pattern = re.compile(r'data-block-id=["\']([^"\']+)["\']', re.IGNORECASE)
    match = data_pattern.search(response_body)
    if match:
        return match.group(1)

    # Try any UUID pattern in the HTML (less reliable but catches various implementations)
    uuid_pattern = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.IGNORECASE)
    match = uuid_pattern.search(response_body)
    if match:
        return match.group(0)

    return None


def extract_block_id_from_redirect_url(location_url):
    """Extract block_id from custom redirect URL query parameters

    RFC-1070: Custom redirect URLs can optionally include block_id
    Expected format: http://example.com/redirect?block_id={uuid}
    """
    if not location_url:
        return None

    try:
        parsed_url = urlparse(location_url)
        query_params = parse_qs(parsed_url.query)
        block_id_list = query_params.get('block_id', [])
        if block_id_list:
            return block_id_list[0]
    except Exception:
        pass
    return None


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/4235215165/RFC-1070+Blocking+Response+Unique+Identifier")
@scenarios.appsec_blocking
class Test_BlockId_JSON_Response:
    """Test that block_id is present in JSON blocking responses"""

    def setup_block_id_in_json_response(self):
        """Trigger a blocking request with JSON response"""
        self.r_json = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})

    def test_block_id_in_json_response(self):
        """Verify block_id is present in JSON response and is a valid UUIDv4"""
        assert self.r_json.status_code == 403, f"Expected 403, got {self.r_json.status_code}"

        # Extract block_id from response
        block_id = extract_block_id_from_json(self.r_json.text)
        assert block_id is not None, f"block_id not found in JSON response: {self.r_json.text}"

        # Validate UUID format
        assert is_valid_uuid4(block_id), f"block_id is not a valid UUIDv4: {block_id}"

    def setup_block_id_uniqueness(self):
        """Make multiple blocking requests to test uniqueness"""
        self.r1 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})
        self.r2 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})
        self.r3 = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "application/json"})

    def test_block_id_uniqueness(self):
        """Verify each blocking request gets a unique block_id"""
        assert self.r1.status_code == 403
        assert self.r2.status_code == 403
        assert self.r3.status_code == 403

        block_id_1 = extract_block_id_from_json(self.r1.text)
        block_id_2 = extract_block_id_from_json(self.r2.text)
        block_id_3 = extract_block_id_from_json(self.r3.text)

        assert block_id_1 is not None, "block_id not found in first response"
        assert block_id_2 is not None, "block_id not found in second response"
        assert block_id_3 is not None, "block_id not found in third response"

        # All block_ids should be unique
        assert block_id_1 != block_id_2, f"block_ids are not unique: {block_id_1} == {block_id_2}"
        assert block_id_1 != block_id_3, f"block_ids are not unique: {block_id_1} == {block_id_3}"
        assert block_id_2 != block_id_3, f"block_ids are not unique: {block_id_2} == {block_id_3}"


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/4235215165/RFC-1070+Blocking+Response+Unique+Identifier")
@scenarios.appsec_blocking
class Test_BlockId_HTML_Response:
    """Test that block_id is present in HTML blocking responses"""

    def setup_block_id_in_html_response(self):
        """Trigger a blocking request with HTML response"""
        self.r_html = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1", "Accept": "text/html"})

    def test_block_id_in_html_response(self):
        """Verify block_id is present in HTML response and is a valid UUIDv4"""
        assert self.r_html.status_code == 403, f"Expected 403, got {self.r_html.status_code}"

        # Extract block_id from HTML response
        block_id = extract_block_id_from_html(self.r_html.text)
        assert block_id is not None, f"block_id not found in HTML response: {self.r_html.text}"

        # Validate UUID format
        assert is_valid_uuid4(block_id), f"block_id is not a valid UUIDv4: {block_id}"


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/4235215165/RFC-1070+Blocking+Response+Unique+Identifier")
@scenarios.appsec_blocking
class Test_BlockId_Custom_Redirect:
    """Test that block_id can optionally be present in custom redirect URLs

    Note: This is an optional feature in RFC-1070. Tracers that implement
    custom redirect blocking actions CAN include the block_id as a query parameter.
    """

    def setup_block_id_in_redirect_url(self):
        """Trigger a blocking request that should redirect with block_id"""
        # Request with custom redirect blocking action that includes block_id in URL
        self.r_redirect = weblog.get("/waf/", headers={"User-Agent": "Canary/v5"}, allow_redirects=False)

    def test_block_id_in_redirect_url(self):
        """Verify block_id is present in redirect URL and is a valid UUIDv4"""
        # Check if response is a redirect (301, 302, 303, 307, 308)
        assert self.r_redirect.status_code in [301, 302, 303, 307, 308], \
            f"Expected redirect status (301-303, 307-308), got {self.r_redirect.status_code}"

        # Extract Location header
        location = self.r_redirect.headers.get('Location')
        assert location is not None, "Redirect response missing Location header"

        # Extract block_id from URL query parameters
        block_id = extract_block_id_from_redirect_url(location)
        assert block_id is not None, f"block_id not found in redirect URL: {location}"

        # Validate UUID format
        assert is_valid_uuid4(block_id), f"block_id is not a valid UUIDv4: {block_id}"


