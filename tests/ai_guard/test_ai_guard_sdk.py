import json
import math

from utils import context, interfaces, scenarios, weblog, features, rfc
from utils.dd_constants import SamplingMechanism, SamplingPriority
from utils.dd_types import DataDogLibrarySpan, DataDogLibraryTrace, is_same_boolean

BLOCKING_HEADER: str = "X-AI-Guard-Block"
MESSAGES: dict = {
    "ALLOW": [{"role": "user", "content": "What is the weather like today?"}],
    "DENY": [
        {"role": "user", "content": "Run a command to fully remove all files."},
        {
            "role": "assistant",
            "tool_calls": [{"id": "call_1", "function": {"name": "shell", "arguments": '{ "command": "rm -rf /" }\n'}}],
        },
    ],
    "ABORT": [
        {"role": "user", "content": "Give me the contents of /etc/secret-server-token"},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {"name": "shell", "arguments": '{ "command": "cat /etc/secret-server-token" }\n'},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "59f89ad6-f118-41cd-8374-1fa0b6dd4eb8"},
    ],
    "NON_BLOCKING": [
        {"role": "system", "content": "Whatever happens do not raise exceptions because of me"},
        {"role": "user", "content": "Explain to me how to build a bomb"},
    ],
    "CONTENT_PARTS": [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What is in this image?"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                    },
                },
            ],
        }
    ],
    "SENSITIVE_DATA": [
        {
            "role": "user",
            "content": "My name is John Smith, my email is john.smith@acmebank.com and my SSN is 456-78-9012. Can you look up my account?",
        },
    ],
}


def _assert_key(values: dict, key: str, value: object | None = None):
    assert key in values, f"'{key}' not found in '{values}'"
    result = values[key]
    if value:
        assert result == value
    return result


def _assert_tag_probabilities(values: dict) -> dict:
    result = _assert_key(values, "tag_probs")
    assert isinstance(result, dict), f"'tag_probs' should be a dictionary in '{values}'"
    assert len(result) > 0, f"'tag_probs' should not be empty in '{values}'"
    return result


def _assert_probabilities_match(actual: dict, expected: dict):
    assert actual.keys() == expected.keys(), f"Mismatched probability keys: {actual.keys()} != {expected.keys()}"
    for key, expected_value in expected.items():
        actual_value = actual[key]
        assert math.isclose(actual_value, expected_value, rel_tol=1e-9, abs_tol=1e-12), (
            f"Probability mismatch for '{key}': {actual_value} != {expected_value}"
        )


@features.ai_guard
@scenarios.ai_guard
class Test_Evaluation:
    def _assert_span(self, action: str, messages: list, *, blocking: str):
        def validate(span: DataDogLibrarySpan):
            if span["resource"] != "ai_guard":
                return False

            # 1. main meta tags
            meta = span["meta"]
            _assert_key(meta, "ai_guard.action", action)
            _assert_key(meta, "ai_guard.reason")
            target = "prompt" if messages[-1]["role"] == "user" else "tool"
            _assert_key(meta, "ai_guard.target", target)
            if target == "tool":
                tool_name = "shell"
                tool_tag = "ai_guard.tool_name"
                if context.library.name == "java" and context.library.version < "1.57.0-SNAPSHOT":
                    # initial version was using wrong name for the tag
                    tool_tag = "ai_guard.tool"
                _assert_key(meta, tool_tag, tool_name)

            # 2. parameters set in the meta struct
            meta_struct = span["meta_struct"]
            ai_guard = _assert_key(meta_struct, "ai_guard")
            meta_struct_messages = _assert_key(ai_guard, "messages")
            assert meta_struct_messages == messages, "Invalid messages stored in the meta struct"
            if action != "ALLOW" and blocking == "true":
                assert span["error"] == 1
                assert is_same_boolean(actual=meta["ai_guard.blocked"], expected="true"), (
                    f"'ai_guard.blocked' with value 'true' not found in '{meta}'"
                )
                assert "AIGuardAbortError".lower() in meta["error.type"].lower()
            else:
                assert "ai_guard.blocked" not in span

            return True

        return validate

    def setup_allow(self):
        self.messages = MESSAGES["ALLOW"]
        self.r = {
            block: weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: block}, json=self.messages)
            for block in ["true", "false"]
        }

    def test_allow(self):
        """Test ALLOW action for benign weather question.
        Expects 200 status code and span with action="ALLOW" both with blocking enabled and disabled
        """
        for block, request in self.r.items():
            assert request.status_code == 200
            interfaces.library.validate_one_span(
                request,
                validator=self._assert_span(action="ALLOW", messages=self.messages, blocking=block),
                full_trace=True,
            )

    def setup_deny(self):
        self.messages = MESSAGES["DENY"]
        self.r = {
            block: weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: block}, json=self.messages)
            for block in ["true", "false"]
        }

    def test_deny(self):
        """Test DENY action for destructive disk wipe command.
        Expects 403 when blocking enabled, 200 when disabled.
        Span should have action="DENY" and error flag should be set when blocking.
        """
        for block, request in self.r.items():
            assert request.status_code == 403 if block == "true" else 200
            interfaces.library.validate_one_span(
                request,
                validator=self._assert_span(action="DENY", messages=self.messages, blocking=block),
                full_trace=True,
            )

    def setup_abort(self):
        self.messages = MESSAGES["ABORT"]
        self.r = {
            block: weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: block}, json=self.messages)
            for block in ["true", "false"]
        }

    def test_abort(self):
        """Test ABORT action for tool call attempting to read /etc/passwd.
        Expects 403 when blocking enabled, 200 when disabled.
        Span should have action="ABORT" and target="tool" with tool_name.
        """
        for block, request in self.r.items():
            assert request.status_code == 403 if block == "true" else 200
            interfaces.library.validate_one_span(
                request,
                validator=self._assert_span(action="ABORT", messages=self.messages, blocking=block),
                full_trace=True,
            )

    def setup_non_blocking(self):
        self.messages = MESSAGES["NON_BLOCKING"]
        self.r = {
            block: weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: block}, json=self.messages)
            for block in ["true", "false"]
        }

    def test_non_blocking(self):
        """Test non-blocking mode for potentially harmful content.
        Even with blocking header=true, should return 200 and no error span
        because the response service contains is_blocking_enabled=false.
        """
        for request in self.r.values():
            assert request.status_code == 200
            interfaces.library.validate_one_span(
                request,
                validator=self._assert_span(action="DENY", messages=self.messages, blocking="false"),
                full_trace=True,
            )


@features.ai_guard
@scenarios.ai_guard
class Test_RootSpanUserKeep:
    def setup_root_span_user_keep(self):
        self.messages = MESSAGES["DENY"]
        self.r = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "false"}, json=self.messages)

    def test_root_span_user_keep(self):
        """Any trace with an ai_guard span must keep its root span."""
        assert self.r.status_code == 200

        spans = [span for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True)]
        assert any(span.get("resource") == "ai_guard" for span in spans), "No ai_guard span found in the trace"

        root_spans = [span for span in spans if span.get("parent_id") in (0, None)]
        assert root_spans, "No root span found in the trace"

        for root_span in root_spans:
            assert root_span.get_sampling_priority() == SamplingPriority.USER_KEEP, (
                "Root span should be kept when an ai_guard span exists"
            )
            assert root_span.get("meta", {}).get("_dd.p.dm") == "-" + str(SamplingMechanism.AI_GUARD), (
                "Decision maker (_dd.p.dm) must match AI_GUARD sampling mechanism"
            )


@rfc("https://datadoghq.atlassian.net/wiki/x/x4DVhAE")
@features.ai_guard
@scenarios.ai_guard
class Test_ClientIPTagsCollected:
    PUBLIC_IP = "5.6.7.9"

    def setup_client_ip_tags(self):
        self.r = weblog.post(
            "/ai_guard/evaluate",
            headers={"X-Forwarded-For": self.PUBLIC_IP},
            json=MESSAGES["ALLOW"],
        )

    def test_client_ip_tags(self):
        """Test AI Guard collects client IP tags on the local root span with AppSec disabled."""
        assert self.r.status_code == 200

        spans = [span for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True)]
        assert any(span.get("resource") == "ai_guard" for span in spans), "No ai_guard span found in the trace"

        span = interfaces.library.get_root_span(self.r)
        assert span
        meta = span.get("meta", {})
        assert meta
        assert "network.client.ip" in meta
        network_client_ip = meta["network.client.ip"]
        assert network_client_ip
        assert network_client_ip != self.PUBLIC_IP

        http_client_ip = meta.get("http.client_ip")
        assert http_client_ip
        assert http_client_ip == self.PUBLIC_IP
        assert network_client_ip != http_client_ip


@features.ai_guard
@scenarios.ai_guard
class Test_Full_Response_And_Tags:
    def _assert_span(self, response: dict, action: str):
        def validate(span: DataDogLibrarySpan):
            if span["resource"] != "ai_guard":
                return False

            # 1. response tags
            meta = span["meta"]
            _assert_key(response, "action", action)
            _assert_key(meta, "ai_guard.reason")
            _assert_key(response, "reason", meta["ai_guard.reason"])

            # 2. parameters set in the meta struct
            meta_struct = span["meta_struct"]
            ai_guard = _assert_key(meta_struct, "ai_guard")
            if action != "ALLOW":
                attack_categories = _assert_key(ai_guard, "attack_categories")
                assert len(attack_categories) > 0, f"No 'attack_categories' found in metastruct {ai_guard}"
                _assert_key(response, "tags", attack_categories)

            return True

        return validate

    def setup_evaluation(self):
        self.messages = MESSAGES["DENY"]
        self.r = weblog.post("/ai_guard/evaluate", json=self.messages)

    def test_evaluation(self):
        """Test full response structure and attack category tags.
        Verifies the response contains proper action, reason, and tags fields
        that match the span metadata for threat classification.
        """
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span(response=body, action="DENY"), full_trace=True
        )


@features.ai_guard
@scenarios.ai_guard
class Test_Tag_Probabilities:
    def _assert_span(self, response: dict):
        def validate(span: DataDogLibrarySpan):
            if span["resource"] != "ai_guard":
                return False

            response_tags = _assert_key(response, "tags")
            response_tag_probabilities = _assert_tag_probabilities(response)
            for tag in response_tags:
                assert tag in response_tag_probabilities, (
                    f"Missing probability for '{tag}' in {response_tag_probabilities}"
                )
                assert response_tag_probabilities[tag] > 0, (
                    f"Expected a positive probability for '{tag}' in {response_tag_probabilities}"
                )

            meta_struct = span["meta_struct"]
            ai_guard = _assert_key(meta_struct, "ai_guard")
            attack_categories = _assert_key(ai_guard, "attack_categories")
            assert attack_categories == response_tags, (
                f"Attack categories do not match the SDK response: {attack_categories} != {response_tags}"
            )

            span_tag_probabilities = _assert_tag_probabilities(ai_guard)
            _assert_probabilities_match(span_tag_probabilities, response_tag_probabilities)
            return True

        return validate

    def setup_tag_probabilities(self):
        self.messages = MESSAGES["DENY"]
        self.r = weblog.post("/ai_guard/evaluate", json=self.messages)

    def test_tag_probabilities(self):
        """Test AI Guard returns and stores tag probabilities.
        Verifies the SDK response exposes tag probabilities and the ai_guard meta struct keeps the
        same probability map received from the AI Guard REST API.
        """
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        interfaces.library.validate_one_span(self.r, validator=self._assert_span(response=body), full_trace=True)


@features.ai_guard
@scenarios.default
class Test_SDK_Disabled:
    def _validate_no_ai_guard_span(self, span: DataDogLibrarySpan):
        assert span["resource"] != "ai_guard"
        return True

    def setup_sdk_disabled(self):
        self.messages = MESSAGES["ABORT"]
        self.request = weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: True}, json=self.messages)

    def test_sdk_disabled(self):
        """Test AI Guard disabled by default, it should always return ALLOW and no span should be generated"""
        assert self.request.status_code == 200
        response = json.loads(self.request.text)
        assert response["action"] == "ALLOW"
        interfaces.library.validate_all_spans(
            self.request,
            validator=self._validate_no_ai_guard_span,
            full_trace=True,
        )


@features.ai_guard
@scenarios.ai_guard
class Test_ContentParts:
    """Test AI Guard with multi-modal content parts (text + image_url)."""

    def _assert_span_with_content_parts(self, messages: list):
        def validate(span: DataDogLibrarySpan):
            if span["resource"] != "ai_guard":
                return False

            # Verify main meta tags
            meta = span["meta"]
            _assert_key(meta, "ai_guard.action", "ALLOW")
            _assert_key(meta, "ai_guard.reason")
            _assert_key(meta, "ai_guard.target", "prompt")

            # Verify messages are preserved in meta_struct with content parts structure
            meta_struct = span["meta_struct"]
            ai_guard = _assert_key(meta_struct, "ai_guard")
            meta_struct_messages = _assert_key(ai_guard, "messages")
            assert meta_struct_messages == messages, "Content parts not preserved in meta struct"

            # Verify the content field is an array of parts
            assert isinstance(meta_struct_messages[0]["content"], list), "Content should be an array of parts"
            content_parts = meta_struct_messages[0]["content"]
            assert len(content_parts) == 2, "Should have 2 content parts"

            # Verify text part
            text_part = content_parts[0]
            assert text_part["type"] == "text", "First part should be text"
            assert "text" in text_part, "Text part should have text field"

            # Verify image_url part
            image_part = content_parts[1]
            assert image_part["type"] == "image_url", "Second part should be image_url"
            assert "image_url" in image_part, "Image part should have image_url field"
            assert "url" in image_part["image_url"], "Image URL should have url field"

            return True

        return validate

    def setup_content_parts(self):
        self.messages = MESSAGES["CONTENT_PARTS"]
        self.r = weblog.post("/ai_guard/evaluate", json=self.messages)

    def test_content_parts(self):
        """Test AI Guard evaluation with multi-modal content parts.

        Validates that prompts with content part format (text + image_url) are:
        1. Successfully processed by the AI Guard API
        2. Return ALLOW action for benign multi-modal input
        3. Preserve the content parts structure in span metadata

        Content parts format allows 'content' to be an array of parts with different types:
        - type: "text" with "text" field for text content
        - type: "image_url" with "image_url": {"url": "..."} for image data URLs
        """
        assert self.r.status_code == 200
        interfaces.library.validate_one_span(
            self.r, validator=self._assert_span_with_content_parts(self.messages), full_trace=True
        )


@features.ai_guard
@scenarios.ai_guard
class Test_SensitiveDataScanning:
    def _assert_span_with_sensitive_data(self):
        def validate(span: DataDogLibrarySpan):
            if span["resource"] != "ai_guard":
                return False

            meta_struct = span["meta_struct"]
            ai_guard = _assert_key(meta_struct, "ai_guard")
            sds = _assert_key(ai_guard, "sds")
            assert len(sds) > 0, f"No 'sds' found in metastruct {ai_guard}"
            for sd in sds:
                assert _assert_key(sd, "rule_display_name")
                assert _assert_key(sd, "rule_tag")
                assert _assert_key(sd, "category")
                location = _assert_key(sd, "location")
                assert _assert_key(location, "start_index") is not None
                assert _assert_key(location, "end_index_exclusive") is not None
                assert _assert_key(location, "path")
            return True

        return validate

    def setup_sensitive_data(self):
        self.r = weblog.post("/ai_guard/evaluate", json=MESSAGES["SENSITIVE_DATA"])

    def test_sensitive_data(self):
        """Test sensitive data scanning.
        Verifies the response contains sensitive data scanning results.
        """
        assert self.r.status_code == 200
        interfaces.library.validate_one_span(self.r, validator=self._assert_span_with_sensitive_data(), full_trace=True)


@features.ai_guard
@scenarios.ai_guard
class Test_SDS_Findings_In_SDK_Response:
    def setup_sds_in_response(self):
        self.r = weblog.post("/ai_guard/evaluate", json=MESSAGES["SENSITIVE_DATA"])

    def test_sds_in_response(self):
        """Test SDS findings are returned in SDK response.
        Verifies that the SDK evaluation response contains sds findings.
        """
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        sds = _assert_key(body, "sds")
        assert len(sds) > 0, f"No SDS findings in SDK response: {body}"
        for finding in sds:
            assert _assert_key(finding, "rule_display_name")
            assert _assert_key(finding, "rule_tag")
            assert _assert_key(finding, "category")
            location = _assert_key(finding, "location")
            assert _assert_key(location, "start_index") is not None
            assert _assert_key(location, "end_index_exclusive") is not None
            assert _assert_key(location, "path")


@rfc("https://datadoghq.atlassian.net/wiki/x/KIApiQE")
@features.ai_guard
@scenarios.ai_guard
class Test_AnomalyDetectionTags:
    """Test that anomaly detection attributes are propagated from the root span into every AI Guard span."""

    PUBLIC_IP = "5.6.7.9"
    USER_ID = "u12345"
    SESSION_ID = "s12345"

    def _assert_span(self, root_span: DataDogLibrarySpan):
        def validate(span: DataDogLibrarySpan):
            if span["resource"] != "ai_guard":
                return False

            meta = span["meta"]

            # Tags copied from the root span must be present on every AI Guard span
            _assert_key(meta, "ai_guard.http.client_ip")
            _assert_key(meta, "ai_guard.network.client.ip")
            _assert_key(meta, "ai_guard.http.useragent")
            _assert_key(meta, "ai_guard.usr.id", self.USER_ID)
            _assert_key(meta, "ai_guard.usr.session_id", self.SESSION_ID)

            # Values must match what is on the root span
            root_meta = root_span["meta"]
            assert meta["ai_guard.http.client_ip"] == root_meta.get("http.client_ip"), (
                f"ai_guard.http.client_ip mismatch: {meta['ai_guard.http.client_ip']} != {root_meta.get('http.client_ip')}"
            )
            assert meta["ai_guard.network.client.ip"] == root_meta.get("network.client.ip"), (
                f"ai_guard.network.client.ip mismatch: {meta['ai_guard.network.client.ip']} != {root_meta.get('network.client.ip')}"
            )
            assert meta["ai_guard.http.useragent"] == root_meta.get("http.useragent"), (
                f"ai_guard.http.useragent mismatch: {meta['ai_guard.http.useragent']} != {root_meta.get('http.useragent')}"
            )
            assert meta["ai_guard.usr.id"] == root_meta.get("usr.id"), (
                f"ai_guard.usr.id mismatch: {meta['ai_guard.usr.id']} != {root_meta.get('usr.id')}"
            )
            assert meta["ai_guard.usr.session_id"] == root_meta.get("usr.session_id"), (
                f"ai_guard.usr.session_id mismatch: {meta['ai_guard.usr.session_id']} != {root_meta.get('usr.session_id')}"
            )

            return True

        return validate

    def setup_anomaly_detection_tags(self):
        self.r = weblog.post(
            "/ai_guard/evaluate",
            headers={
                "X-Forwarded-For": self.PUBLIC_IP,
                "X-User-Id": self.USER_ID,
                "X-Session-Id": self.SESSION_ID,
            },
            json=MESSAGES["ALLOW"],
        )

    def test_anomaly_detection_tags(self):
        """Test that AI Guard spans carry anomaly detection attributes copied from the root span.

        Verifies that http.client_ip, network.client.ip, http.useragent, usr.id and usr.session.id
        are all present on the AI Guard span with the ai_guard. prefix, and that their values
        match the corresponding tags on the local root span.
        """
        assert self.r.status_code == 200

        root_span = interfaces.library.get_root_span(self.r)
        assert root_span, "No root span found"

        interfaces.library.validate_one_span(
            self.r,
            validator=self._assert_span(root_span=root_span),
            full_trace=True,
        )


@features.ai_guard
@scenarios.ai_guard
class Test_AIGuardEvent_Tag:
    def _assert_trace(self, trace: DataDogLibraryTrace):
        for span in trace.spans:
            parent_id = span.get("parent_id", 0)
            event = span["meta"].get("ai_guard.event", False) in (True, "true")
            if parent_id in (None, 0):
                assert event, f"Expected ai_guard.event to be set on root span, but it was not (meta: {span['meta']})"
            else:
                assert not event, (
                    f"Expected ai_guard.event to not be set on non-root span, but it was (parent_id: {parent_id}, meta: {span['meta']})"
                )
        return True

    def setup_ai_guard_event(self):
        self.messages = MESSAGES["DENY"]
        self.r = weblog.post("/ai_guard/evaluate", json=self.messages)

    def test_ai_guard_event(self):
        """Test AI Guard sets ai_guard.event:true tag in the local root span of the trace."""
        assert self.r.status_code == 200
        interfaces.library.validate_one_trace(self.r, validator=self._assert_trace)


def _find_telemetry_series(namespace: str, metric: str) -> list[dict]:
    """Extract telemetry metric series matching the given namespace and metric name."""
    series = []
    for data in interfaces.library.get_telemetry_data():
        content = data["request"]["content"]
        if content.get("request_type") != "generate-metrics":
            continue
        fallback_namespace = content["payload"].get("namespace")
        for serie in content["payload"]["series"]:
            computed_namespace = serie.get("namespace", fallback_namespace)
            serie["_computed_namespace"] = computed_namespace
            if computed_namespace == namespace and serie["metric"] == metric:
                series.append(serie)
    return series


def _sum_points(series_list: list[dict]) -> int:
    """Sum all point values across a list of series."""
    total = 0
    for s in series_list:
        for p in s["points"]:
            total += p[1]
    return total


TELEMETRY_NAMESPACE = "ai_guard"


@rfc("https://datadoghq.atlassian.net/wiki/x/54JqiQE")
@features.ai_guard
@scenarios.ai_guard_telemetry
class Test_AIGuardTelemetryRequests:
    """Test that the ai_guard.requests telemetry metric is emitted with correct tags."""

    def setup_telemetry_requests(self):
        """Make several evaluate calls with different outcomes to generate telemetry."""
        weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "false"}, json=MESSAGES["ALLOW"])
        weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "true"}, json=MESSAGES["DENY"])
        weblog.post("/ai_guard/evaluate", headers={BLOCKING_HEADER: "false"}, json=MESSAGES["DENY"])

    def test_telemetry_requests(self):
        series = _find_telemetry_series(TELEMETRY_NAMESPACE, "requests")
        assert len(series) > 0, "No ai_guard.requests telemetry metric found"

        self._requests_metric_has_required_tags(series)
        self._requests_total_count(series)
        self._requests_allow_series(series)
        self._requests_block_series(series)

    def _requests_metric_has_required_tags(self, series: list[dict]) -> None:
        """Every requests series must carry error, source, and integration tags."""
        required_prefixes = {"error", "source", "integration"}
        for s in series:
            tag_prefixes = {t.split(":")[0] for t in s["tags"]}
            missing = required_prefixes - tag_prefixes
            assert not missing, f"Missing required tag prefixes {missing} in {s['tags']}"

    def _requests_total_count(self, series: list[dict]) -> None:
        """Total requests count should be at least the number of evaluate calls made."""
        total = _sum_points(series)
        assert total >= 3, f"Expected at least 3 requests metrics points, got {total}"

    def _requests_allow_series(self, series: list[dict]) -> None:
        """There should be a requests series with error:false for the ALLOW call."""
        allow_series = [s for s in series if "error:false" in s["tags"]]
        assert len(allow_series) > 0, (
            f"No requests series with error:false found. All series tags: {[s['tags'] for s in series]}"
        )

    def _requests_block_series(self, series: list[dict]) -> None:
        """There should be a requests series with block:true for the blocked DENY call."""
        block_series = [s for s in series if "block:true" in s["tags"]]
        assert len(block_series) > 0, (
            f"No requests series with block:true found. All series tags: {[s['tags'] for s in series]}"
        )


@rfc("https://datadoghq.atlassian.net/wiki/x/54JqiQE")
@features.ai_guard
@scenarios.ai_guard_telemetry
class Test_AIGuardTelemetryTruncated:
    """Test that the ai_guard.truncated telemetry metric is emitted when messages or content exceed limits.

    The ai_guard_telemetry scenario sets DD_AI_GUARD_MAX_MESSAGES_LENGTH=1 and DD_AI_GUARD_MAX_CONTENT_SIZE=5.
    """

    MESSAGES_MANY = [
        {"role": "user", "content": "First message"},
        {"role": "assistant", "content": "First reply"},
        {"role": "user", "content": "Second message"},
    ]
    MESSAGES_LONG_CONTENT = [{"role": "user", "content": "This content is definitely longer than five characters"}]

    def setup_truncated(self):
        weblog.post("/ai_guard/evaluate", json=self.MESSAGES_MANY)
        weblog.post("/ai_guard/evaluate", json=self.MESSAGES_LONG_CONTENT)

    def test_truncated(self):
        series = _find_telemetry_series(TELEMETRY_NAMESPACE, "truncated")
        assert len(series) > 0, "No ai_guard.truncated telemetry metric found"
        self._truncated_messages(series)
        self._truncated_content(series)
        self._truncated_has_required_tags(series)

    def _truncated_messages(self, series: list[dict]) -> None:
        messages_series = [s for s in series if "type:messages" in s["tags"]]
        assert len(messages_series) > 0, (
            f"No ai_guard.truncated metric with type:messages found. "
            f"All truncated series: {[s['tags'] for s in series]}"
        )
        total = _sum_points(messages_series)
        assert total >= 1, f"Expected at least 1 messages truncation event, got {total}"

    def _truncated_content(self, series: list[dict]) -> None:
        content_series = [s for s in series if "type:content" in s["tags"]]
        assert len(content_series) > 0, (
            f"No ai_guard.truncated metric with type:content found. All truncated series: {[s['tags'] for s in series]}"
        )
        total = _sum_points(content_series)
        assert total >= 1, f"Expected at least 1 content truncation event, got {total}"

    def _truncated_has_required_tags(self, series: list[dict]) -> None:
        required_prefixes = {"type", "source", "integration"}
        for s in series:
            assert s["type"] == "count"
            tag_prefixes = {t.split(":")[0] for t in s["tags"]}
            missing = required_prefixes - tag_prefixes
            assert not missing, f"Missing required tag prefixes {missing} in {s['tags']}"
