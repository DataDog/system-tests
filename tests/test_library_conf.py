# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features
from utils._context.header_tag_vars import *
from utils import remote_config as rc
import json
import pprint


# basic / legacy tests, just tests user-agent can be received as a tag
@features.security_events_metadata
class Test_HeaderTags:
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags_basic(self):
        """Test that http.request.headers.user-agent is in all web spans"""

        for _, span in interfaces.library.get_root_spans():
            if span.get("type") == "web":
                assert "http.request.headers.user-agent" in span.get("meta", {})


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Short:
    """Validates that the short, header name only, format for specifying headers correctly tags spans"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_SHORT: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_SHORT: HEADER_VAL_BASIC}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Long:
    """Validates that input in `<header>:<tag_name>` format correctly tags spans"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_LONG: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_LONG: HEADER_VAL_BASIC}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Whitespace_Header:
    """Validates that leading/trailing whitespaces are trimmed on the header values given to DD_TRACE_HEADER_TAGS
    e.g, ' header ' in DD_TRACE_HEADER_TAGS=' header ' becomes 'header' and is expected to match req.header of 'header'"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_WHITESPACE_HEADER: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_WHITESPACE_HEADER: HEADER_VAL_BASIC}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Whitespace_Tag:
    """Validates that leading/trailing whitespaces on the Input to DD_TRACE_HEADER_TAGS are
    trimmed on mapping parts, but whitespaces in between non-whitespace chars are left in-tact."""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_WHITESPACE_TAG: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_WHITESPACE_TAG: HEADER_VAL_BASIC}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Whitespace_Val_Short:
    """Validates that between-char whitespaces in header values are not removed,
    but leading/trailing whitespace is stripped, using short form input"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_WHITESPACE_VAL_SHORT: HEADER_VAL_WHITESPACE_VAL_SHORT}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_WHITESPACE_VAL_SHORT: HEADER_VAL_WHITESPACE_VAL_SHORT.strip()}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Whitespace_Val_Long:
    """Validates that between-char whitespaces in header values are not removed,
    but leading/trailing whitespace is stripped, using long form input"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_WHITESPACE_VAL_LONG: HEADER_VAL_WHITESPACE_VAL_LONG}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_WHITESPACE_VAL_LONG: HEADER_VAL_WHITESPACE_VAL_LONG.strip()}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags_invalid
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Colon_Leading:
    """Validates that Input to DD_TRACE_HEADER_TAGS with leading colon results in 0 additional span tags"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_COLON_LEADING: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        nottags = [
            HEADER_NAME_COLON_LEADING,
            TAG_COLON_LEADING,
            CONFIG_COLON_LEADING.split(":")[0],
            CONFIG_COLON_LEADING.split(":")[1],
        ]

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in nottags:
                assert tag not in span["meta"]


@scenarios.library_conf_custom_header_tags_invalid
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Colon_Trailing:
    """Validates that DD_TRACE_HEADER_TAGS input that contains a leading or trailing colon results in 0 additional span tags"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_COLON_TRAILING: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        nottags = [
            HEADER_NAME_COLON_TRAILING,
            TAG_COLON_TRAILING,
            CONFIG_COLON_TRAILING.split(":")[0],
            CONFIG_COLON_TRAILING.split(":")[1],
        ]

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in nottags:
                assert tag not in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_DynamicConfig:
    def setup_tracing_client_http_header_tags(self):
        path, config = self.get_rc_params(
            {
                "tracing_header_tags": [
                    {"header": "X-Test-Header", "tag_name": "test_header_rc"},
                    {"header": "X-Test-Header-2", "tag_name": "test_header_rc2"},
                    {"header": "Content-Length", "tag_name": ""},
                ]
            }
        )
        rc.rc_state.reset().set_config(path, config).apply()
        self.req1 = weblog.get(
            "/status?code=202",
            headers={
                "X-Test-Header": "1",
                "X-Test-Header-2": "2",
                "Content-Length": "0",
                HEADER_NAME_SHORT: HEADER_VAL_BASIC,
            },
        )

        path, config = self.get_rc_params({})
        rc.rc_state.reset().set_config(path, config).apply()
        self.req2 = weblog.get(
            "/status?code=202",
            headers={
                "X-Test-Header": "1",
                "X-Test-Header-2": "2",
                "Content-Length": "0",
                HEADER_NAME_SHORT: HEADER_VAL_BASIC,
            },
        )

    def test_tracing_client_http_header_tags(self):
        """Ensure the tracing http header tags can be set via RC.

        Testing is done using a http client request RPC and asserting the span tags.

        Requests are made to the test agent.
        """
        # Validate the spans generated by the first request
        spans = [span for _, _, span in interfaces.library.get_spans(request=self.req1, full_trace=True)]
        for s in spans:
            if "/status" in s["resource"]:
                # Header tags set via remote config
                assert s["meta"].get("test_header_rc")
                assert s["meta"].get("test_header_rc2")
                assert s["meta"].get("http.request.headers.content-length")
                # Does not have headers set via Enviorment variables
                assert TAG_SHORT not in s["meta"]
                break
        else:
            assert False, f"A span with /status in the resource name was not found {spans}"

        # Validate the spans generated by the second request
        spans = [span for _, _, span in interfaces.library.get_spans(request=self.req2, full_trace=True)]
        for s in spans:
            if "/status" in s["resource"]:
                # Headers tags set via remote config
                assert s["meta"].get(TAG_SHORT) == HEADER_VAL_BASIC
                # Does not have headers set via remote config
                assert "test_header_rc" not in s["meta"], s["meta"]
                assert "test_header_rc2" not in s["meta"], s["meta"]
                assert "http.request.headers.content-length" in s["meta"], s["meta"]
                break
        else:
            assert False, f"A span with /status in the resource name was not found {spans}"

    def get_rc_params(self, header_tags):
        config = {
            "action": "enable",
            "service_target": {"service": "weblog", "env": "system-tests"},
            "lib_config": header_tags,
        }
        id = hash(json.dumps(config))
        return f"datadog/2/APM_TRACING/{id}/config", config


@scenarios.default
class Test_ExtractBehavior_Default:
    def setup_single_tracecontext(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-11111111111111110000000000000001-0000000000000001-01",
                "tracestate": "dd=s:2;t.dm:-4,foo=1",
                "x-b3-traceid": "11111111111111110000000000000001",
                "x-b3-spanid": "0000000000000001",
                "x-b3-sampled": "1",
                "baggage": "key1=value1",
            },
        )

    def test_single_tracecontext(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert span.get("traceID") == "1"
        assert span.get("parentID") == "1"
        assert "spanLinks" not in span or len(span["spanLinks"]) == 0

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] == "1"
        assert "_dd.p.tid=1111111111111111" in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]

    def setup_multiple_tracecontexts(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "2",
                "x-datadog-parent-id": "2",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-12345678901234567890123456789012-1234567890123456-01",
                "x-b3-traceid": "22222222222222223333333333333333",
                "x-b3-spanid": "4444444444444444",
                "x-b3-sampled": "1",
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert span.get("traceID") == "2"
        assert span.get("parentID") == "2"

        # Test the extracted span links: One span link per conflicting trace context
        assert len(span.get("spanLinks")) == 2

        # Assert the W3C Trace Context (conflicting trace context) span link
        link = span.get("spanLinks")[0]
        assert link["traceID"] == "8687463697196027922" # int(0x7890123456789012)
        assert link["spanID"] == "1311768467284833366" # int (0x1234567890123456)
        assert link["traceIDHigh"] == "1311768467284833366" # int(0x1234567890123456)
        assert link["attributes"] == {"reason": "terminated_context", "context_headers": "tracecontext"}

        # Assert the b3 (conflicting trace context) span link
        link = span.get("spanLinks")[1]
        assert link["traceID"] == "3689348814741910323" # int(0x3333333333333333)
        assert link["spanID"] == "4919131752989213764" # int (0x4444444444444444)
        assert link["traceIDHigh"] == "2459565876494606882" # int(0x2222222222222222)
        assert link["attributes"] == {"reason": "terminated_context", "context_headers": "b3multi"}

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] == "2"
        assert "_dd.p.tid=1111111111111111" in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]


@scenarios.tracing_config_nondefault
class Test_ExtractBehavior_Restart:
    def setup_single_tracecontext(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-11111111111111110000000000000001-0000000000000001-01",
                "tracestate": "dd=s:2;t.dm:-4,foo=1",
                "x-b3-traceid": "11111111111111110000000000000001",
                "x-b3-spanid": "0000000000000001",
                "x-b3-sampled": "1",
                "baggage": "key1=value1",
            },
        )

    def test_single_tracecontext(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert span.get("traceID") != "1"
        assert span.get("parentID") is None

        # Test the extracted span links: One span link for the incoming (Datadog trace context).
        # In the case that span links are generated for conflicting trace contexts, those span links
        # are not included in the new trace context
        assert len(span.get("spanLinks")) == 1

        # Assert the Datadog (restarted) span link
        link = span.get("spanLinks")[0]
        assert link["traceID"] == "1"
        assert link["spanID"] == "1"
        assert link["traceIDHigh"] == "1229782938247303441"
        assert link["attributes"] == {"reason": "propagation_behavior_extract=restart", "context_headers": "datadog"}

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]

    def setup_multiple_tracecontexts(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-12345678901234567890123456789012-1234567890123456-01",
                "x-b3-traceid": "22222222222222223333333333333333",
                "x-b3-spanid": "4444444444444444",
                "x-b3-sampled": "1",
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert span.get("traceID") != "1" and span.get("traceID") != "8687463697196027922" and span.get("traceID") != "3689348814741910323"
        assert span.get("parentID") is None

        # Test the extracted span links: One span link for the incoming (Datadog trace context).
        # In the case that span links are generated for conflicting trace contexts, those span links
        # are not included in the new trace context
        assert len(span.get("spanLinks")) == 1

        # Assert the Datadog (restarted) span link
        link = span.get("spanLinks")[0]
        assert link["traceID"] == "1"
        assert link["spanID"] == "1"
        assert link["traceIDHigh"] == "1229782938247303441"
        assert link["attributes"] == {"reason": "propagation_behavior_extract=restart", "context_headers": "datadog"}

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]


@scenarios.tracing_config_nondefault_2
class Test_ExtractBehavior_Ignore:
    def setup_single_tracecontext(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-11111111111111110000000000000001-0000000000000001-01",
                "tracestate": "dd=s:1;t.dm:-4,foo=1",
                "x-b3-traceid": "11111111111111110000000000000001",
                "x-b3-spanid": "0000000000000001",
                "x-b3-sampled": "1",
                "baggage": "key1=value1",
            },
        )

    def test_single_tracecontext(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the local span context
        span = spans[0]
        assert span.get("traceID") != "1"
        assert span.get("parentID") is None
        assert "spanLinks" not in span or len(span.get("spanLinks")) == 0

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "baggage" not in data["request_headers"]

    def setup_multiple_tracecontexts(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "2",
                "x-datadog-parent-id": "2",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-12345678901234567890123456789012-1234567890123456-01",
                "x-b3-traceid": "22222222222222223333333333333333",
                "x-b3-spanid": "4444444444444444",
                "x-b3-sampled": "1",
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the local span context
        span = spans[0]
        assert span.get("traceID") != "1" and span.get("traceID") != "8687463697196027922" and span.get("traceID") != "3689348814741910323"
        assert span.get("parentID") is None
        assert "spanLinks" not in span or len(span.get("spanLinks")) == 0

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "2"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "baggage" not in data["request_headers"]


@scenarios.tracing_config_nondefault_3
class Test_ExtractBehavior_Restart_With_Extract_First:
    def setup_single_tracecontext(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-11111111111111110000000000000001-0000000000000001-01",
                "tracestate": "dd=s:2;t.dm:-4,foo=1",
                "x-b3-traceid": "11111111111111110000000000000001",
                "x-b3-spanid": "0000000000000001",
                "x-b3-sampled": "1",
                "baggage": "key1=value1",
            },
        )

    def test_single_tracecontext(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert span.get("traceID") != "1"
        assert span.get("parentID") is None

        # Test the extracted span links: One span link for the incoming (Datadog trace context).
        # In the case that span links are generated for conflicting trace contexts, those span links
        # are not included in the new trace context
        assert len(span.get("spanLinks")) == 1

        # Assert the Datadog (restarted) span link
        link = span.get("spanLinks")[0]
        assert link["traceID"] == "1"
        assert link["spanID"] == "1"
        assert link["traceIDHigh"] == "1229782938247303441"
        assert link["attributes"] == {"reason": "propagation_behavior_extract=restart", "context_headers": "datadog"}

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]

    def setup_multiple_tracecontexts(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-12345678901234567890123456789012-1234567890123456-01",
                "x-b3-traceid": "22222222222222223333333333333333",
                "x-b3-spanid": "4444444444444444",
                "x-b3-sampled": "1",
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert span.get("traceID") != "1" and span.get("traceID") != "8687463697196027922" and span.get("traceID") != "3689348814741910323"
        assert span.get("parentID") is None

        # Test the extracted span links: One span link for the incoming (Datadog trace context).
        # In the case that span links are generated for conflicting trace contexts, those span links
        # are not included in the new trace context
        assert len(span.get("spanLinks")) == 1

        # Assert the Datadog (restarted) span link
        link = span.get("spanLinks")[0]
        assert link["traceID"] == "1"
        assert link["spanID"] == "1"
        assert link["traceIDHigh"] == "1229782938247303441"

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]
