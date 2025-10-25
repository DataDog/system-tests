# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import interfaces, scenarios, features, weblog, context, bug, remote_config as rc
from utils.dd_constants import Capabilities


# Remote config configurations for extended data collection
EXTENDED_DATA_COLLECTION_ACTION = (
    "datadog/2/ASM/actions/config",
    {
        "actions": [
            {
                "id": "extended_data_collection_example",
                "parameters": {"max_collected_headers": 50},
                "type": "extended_data_collection",
            }
        ]
    },
)

EXTENDED_DATA_COLLECTION_RULE = (
    "datadog/2/ASM_DD/rules/config",
    {
        "rules": [
            {
                "id": "test-rule-id-1",
                "name": "test-rule-name-1",
                "tags": {"type": "a", "category": "custom"},
                "conditions": [
                    {
                        "parameters": {
                            "inputs": [{"address": "server.request.query"}, {"address": "server.request.body"}],
                            "list": ["collect"],
                        },
                        "operator": "phrase_match",
                    }
                ],
                "transformers": ["lowercase"],
                "on_match": ["extended_data_collection_example"],
            }
        ]
    },
)


def assert_body_property(body, prop, expected_value) -> None:
    if context.library.name == "java":
        assert body.get(prop)[0] == expected_value
    else:
        assert body.get(prop) == expected_value


@features.appsec_extended_data_collection
@scenarios.appsec_api_security_rc
class Test_ExtendedDataCollectionCapability:
    """Validate that ASM_EXTENDED_DATA_COLLECTION (44) capability is sent"""

    def test_extended_data_collection_capability(self):
        interfaces.library.assert_rc_capability(Capabilities.ASM_EXTENDED_DATA_COLLECTION)


@features.appsec_extended_data_collection
@scenarios.appsec_api_security_rc
class Test_ExtendedRequestHeadersDataCollection:
    """Test extended data collection using remote config rules and actions"""

    def setup_extended_data_collection_with_rc(self):
        """Setup test with remote config for extended data collection"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Make a request that triggers the extended data collection rule
        self.response = weblog.get(
            "/headers",
            params={"param": "collect"},
            headers={
                "X-My-Header-1": "value1",
                "X-My-Header-2": "value2",
                "X-My-Header-3": "value3",
                "X-My-Header-4": "value4",
                "Content-Type": "text/html",
            },
        )

    def test_extended_data_collection_with_rc(self):
        """Test that extended data collection works when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended data collection is working by checking span metadata
        span = interfaces.library.get_root_span(request=self.response)
        meta = span.get("meta", {})

        # Check that extended headers are collected when the rule matches
        assert meta.get("http.request.headers.x-my-header-1") == "value1"
        assert meta.get("http.request.headers.x-my-header-2") == "value2"
        assert meta.get("http.request.headers.x-my-header-3") == "value3"
        assert meta.get("http.request.headers.x-my-header-4") == "value4"
        assert meta.get("http.request.headers.content-type") == "text/html"

        # Check that no headers were discarded (within the 50 limit)
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.request.header_collection.discarded") is None

    def setup_no_extended_data_collection_without_event(self):
        """Setup test with remote config for extended data collection with headers redaction enabled"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Make a request that does not trigger the extended data collection rule
        self.response = weblog.get(
            "/headers",
            headers={
                "X-My-Header-1": "value1",
                "X-My-Header-2": "value2",
                "X-My-Header-3": "value3",
                "X-My-Header-4": "value4",
                "Content-Type": "text/html",
            },
        )

    def test_no_extended_data_collection_without_event(self):
        """Test that extended data collection with headers redaction works when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended data collection is ignored by checking span metadata
        span = interfaces.library.get_root_span(request=self.response)
        meta = span.get("meta", {})

        # Check that extended headers are NOT collected when there is no event
        assert meta.get("http.request.headers.x-my-header-1") is None
        assert meta.get("http.request.headers.x-my-header-2") is None
        assert meta.get("http.request.headers.x-my-header-3") is None
        assert meta.get("http.request.headers.x-my-header-4") is None

        # Standard headers should still be collected
        assert meta.get("http.request.headers.content-type") == "text/html"

        # Check that no headers were discarded (within the 50 limit)
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.request.header_collection.discarded") is None

    def setup_extended_data_collection_with_rc_header_limit(self):
        """Setup test with remote config for extended data collection to test header limit"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Generate 51 headers with the pattern "X-My-Header-<n>": "value<n>"
        headers = {f"X-My-Header-{i}": f"value{i}" for i in range(1, 51)}
        headers = {
            **headers,
            "Content-Type": "text/html",
        }

        # Make a request that triggers the extended data collection rule with many headers
        self.response = weblog.get("/headers", params={"param": "collect"}, headers=headers)

    def test_extended_data_collection_with_rc_header_limit(self):
        """Test that extended data collection respects the 50 header limit when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended data collection header limit is working by checking span metadata
        span = interfaces.library.get_root_span(request=self.response)
        meta = span.get("meta", {})

        # Ensure no more than 50 meta entries start with "http.request.headers."
        header_keys = [k for k in meta if k.startswith("http.request.headers.")]
        assert len(header_keys) == 50, f"Expected 50 collected headers, got {len(header_keys)}: {header_keys}"

        # Ensure allowed headers are collected
        assert meta.get("http.request.headers.content-type") == "text/html"

        metrics = span.get("metrics", {})

        # Confirm _dd.appsec.request.header_collection.discarded exists and is > 0
        discarded = metrics.get("_dd.appsec.request.header_collection.discarded")
        assert discarded is not None
        assert discarded > 0

    def setup_extended_data_collection_with_rc_and_authentication_headers(self):
        """Setup test with remote config for extended data collection"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Make a request that triggers the extended data collection rule
        self.response = weblog.get(
            "/headers",
            params={"param": "collect"},
            headers={
                "Authorization": "value1",
                "Proxy-Authorization": "value2",
                "WWW-Authenticate": "value3",
                "Proxy-Authenticate": "value4",
                "Authentication-Info": "value5",
                "Proxy-Authentication-Info": "value6",
                "Cookie": "value7",
                "Set-Cookie": "value8",
                "Content-Type": "text/html",
            },
        )

    def test_extended_data_collection_with_rc_and_authentication_headers(self):
        """Test that extended data collection works when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended data collection is working by checking span metadata
        span = interfaces.library.get_root_span(request=self.response)
        meta = span.get("meta", {})

        # Check that extended headers are redacted
        assert meta.get("http.request.headers.authorization") == "<redacted>"
        assert meta.get("http.request.headers.proxy-authorization") == "<redacted>"
        assert meta.get("http.request.headers.www-authenticate") == "<redacted>"
        assert meta.get("http.request.headers.proxy-authenticate") == "<redacted>"
        assert meta.get("http.request.headers.authentication-info") == "<redacted>"
        assert meta.get("http.request.headers.proxy-authentication-info") == "<redacted>"
        assert meta.get("http.request.headers.cookie") == "<redacted>"
        assert meta.get("http.request.headers.set-cookie") == "<redacted>"
        assert meta.get("http.request.headers.content-type") == "text/html"

        # Check that no headers were discarded (within the 50 limit)
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.request.header_collection.discarded") is None


@features.appsec_extended_data_collection
@scenarios.appsec_api_security_rc
class Test_ExtendedResponseHeadersDataCollection:
    """Test extended response headers data collection using remote config rules and actions"""

    def setup_extended_response_headers_collection_with_rc(self):
        """Setup test with remote config for extended response headers data collection"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Make a request that triggers the extended data collection rule
        self.response = weblog.get(
            "/customResponseHeaders",
            params={"param": "collect"},
        )

    def test_extended_response_headers_collection_with_rc(self):
        """Test that extended response headers data collection works when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended response headers data collection is working by checking span metadata
        span = interfaces.library.get_root_span(request=self.response)
        meta = span.get("meta", {})

        # Check that extended response headers are collected when the rule matches
        assert meta.get("http.response.headers.x-test-header-1") == "value1"
        assert meta.get("http.response.headers.x-test-header-2") == "value2"
        assert meta.get("http.response.headers.x-test-header-3") == "value3"
        assert meta.get("http.response.headers.x-test-header-4") == "value4"
        assert meta.get("http.response.headers.content-language") == "en-US"

        # Check that no response headers were discarded (within the 50 limit)
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.response.header_collection.discarded") is None

    def setup_no_extended_response_headers_collection_without_event(self):
        """Setup test with remote config for extended response headers data collection but without triggering the rule"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Make a request that does NOT trigger the extended data collection rule
        self.response = weblog.get(
            "/customResponseHeaders",
        )

    def test_no_extended_response_headers_collection_without_event(self):
        """Test that extended response headers data collection does not work when the rule is not triggered"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended response headers data collection is not working when rule is not triggered
        span = interfaces.library.get_root_span(request=self.response)
        meta = span.get("meta", {})

        # Check that extended response headers are NOT collected when the rule is not triggered
        assert meta.get("http.response.headers.x-test-header-1") is None
        assert meta.get("http.response.headers.x-test-header-2") is None
        assert meta.get("http.response.headers.x-test-header-3") is None
        assert meta.get("http.response.headers.x-test-header-4") is None

        # response headers are not collected by default
        assert meta.get("http.response.headers.content-language") is None

        # Check that no response headers were discarded (within the 50 limit)
        metrics = span.get("metrics", {})
        assert metrics.get("_dd.appsec.response.header_collection.discarded") is None

    def setup_extended_response_headers_collection_with_rc_header_limit(self):
        """Setup test with remote config for extended response headers data collection to test header limit"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Generate 50 response headers with the pattern "X-Test-Header-<n>": "value<n>"
        self.response = weblog.get(
            "/exceedResponseHeaders",
            params={"param": "collect"},
        )

    def test_extended_response_headers_collection_with_rc_header_limit(self):
        """Test that extended response headers data collection respects the 50 header limit when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended response headers data collection header limit is working by checking span metadata
        span = interfaces.library.get_root_span(request=self.response)
        meta = span.get("meta", {})

        # Ensure exactly 50 meta entries start with "http.response.headers."
        header_keys = [k for k in meta if k.startswith("http.response.headers.")]
        assert len(header_keys) == 50, f"Expected 50 collected response headers, got {len(header_keys)}: {header_keys}"

        # Ensure allowed response headers are collected
        assert meta.get("http.response.headers.content-language") == "en-US"

        metrics = span.get("metrics", {})
        # Confirm _dd.appsec.response.header_collection.discarded exists and is > 0
        discarded = metrics.get("_dd.appsec.response.header_collection.discarded")
        assert discarded is not None
        assert discarded > 0

    def setup_extended_data_collection_with_rc_and_authentication_headers(self):
        """Setup test with remote config for extended response headers data collection to test header limit"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Generate 50 headers with the pattern "X-Test-Header-<n>": "value<n>"
        self.response = weblog.get(
            "/authorization_related_headers",
            params={"param": "collect"},
        )

    def test_extended_data_collection_with_rc_and_authentication_headers(self):
        """Test that extended response headers data collection respects the 50 header limit when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended response headers data collection header limit is working by checking span metadata
        span = interfaces.library.get_root_span(request=self.response)
        meta = span.get("meta", {})

        # Check that extended headers are redacted
        assert meta.get("http.response.headers.authorization") == "<redacted>"
        assert meta.get("http.response.headers.proxy-authorization") == "<redacted>"
        assert meta.get("http.response.headers.www-authenticate") == "<redacted>"
        assert meta.get("http.response.headers.proxy-authenticate") == "<redacted>"
        assert meta.get("http.response.headers.authentication-info") == "<redacted>"
        assert meta.get("http.response.headers.proxy-authentication-info") == "<redacted>"
        assert meta.get("http.response.headers.cookie") == "<redacted>"
        assert meta.get("http.response.headers.set-cookie") == "<redacted>"


@features.appsec_extended_data_collection
@scenarios.appsec_api_security_rc
class Test_ExtendedRequestBodyCollection:
    """Test extended request body data collection using remote config rules and actions"""

    def setup_extended_request_body_collection(self):
        """Setup test with remote config for extended request body data collection"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Make a request that triggers the extended data collection rule
        self.response = weblog.post(
            "/tag_value/extended_body_collection/200", data={"param": "collect", "body_key": "body_value"}
        )

    def test_extended_request_body_collection(self):
        """Test that extended request body data collection works when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended request body data collection is working by checking span meta_struct
        span = interfaces.library.get_root_span(request=self.response)
        meta_struct = span.get("meta_struct", {})

        # Check that request body is collected in meta_struct when the rule matches
        body = meta_struct.get("http.request.body")
        assert body is not None

        # Verify the body content based on library
        assert_body_property(body, "body_key", "body_value")
        assert_body_property(body, "param", "collect")

    def setup_no_extended_request_body_collection_without_event(self):
        """Setup test with remote config for extended request body data collection but without triggering the rule"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Make a request that does NOT trigger the extended data collection rule
        self.response = weblog.post("/tag_value/extended_body_collection/200", data={"body_key": "body_value"})

    def test_no_extended_request_body_collection_without_event(self):
        """Test that extended request body data collection does not work when the rule is not triggered"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended request body data collection is not working when rule is not triggered
        span = interfaces.library.get_root_span(request=self.response)
        meta_struct = span.get("meta_struct", {})

        # Check that request body is NOT collected when the rule is not triggered
        body = meta_struct.get("http.request.body")
        assert body is None

    def setup_extended_request_body_collection_truncated(self):
        """Setup test with remote config for extended request body data collection with truncated body"""
        # Configure remote config with extended data collection action and rule
        self.config_state = (
            rc.rc_state.reset()
            .set_config(*EXTENDED_DATA_COLLECTION_ACTION)
            .set_config(*EXTENDED_DATA_COLLECTION_RULE)
            .apply()
        )

        # Make a request that triggers the extended data collection rule with a large body
        self.response = weblog.post(
            "/tag_value/extended_body_collection/200", data={"param": "collect", "body_key": "A" * 5000}
        )

    @bug(library="java", weblog_variant="vertx3", reason="APPSEC-57811")
    def test_extended_request_body_collection_truncated(self):
        """Test that extended request body data collection properly truncates large bodies when configured via remote config"""
        # Verify remote config was applied successfully
        assert self.config_state.state == rc.ApplyState.ACKNOWLEDGED

        # Verify the request was processed
        assert self.response.status_code == 200

        # Verify extended request body data collection with truncation is working by checking span meta_struct
        span = interfaces.library.get_root_span(request=self.response)
        meta_struct = span.get("meta_struct", {})

        # Check that request body is collected in meta_struct when the rule matches
        body = meta_struct.get("http.request.body")
        assert body is not None

        # Verify the body content is truncated
        assert_body_property(body, "body_key", "A" * 4096)
        assert_body_property(body, "param", "collect")

        # Verify the body size exceed tag is set
        meta = span.get("meta", {})
        assert meta.get("_dd.appsec.request_body_size.exceeded") == "true"
