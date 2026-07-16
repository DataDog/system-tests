# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import pytest
from utils import weblog, interfaces, scenarios, features, logger
from utils.dd_types import DataDogAgentSpan, AgentTraceFormat
from utils._context.header_tag_vars import (
    CONFIG_COLON_LEADING,
    CONFIG_COLON_TRAILING,
    HEADER_NAME_COLON_LEADING,
    HEADER_NAME_COLON_TRAILING,
    HEADER_NAME_LONG,
    HEADER_NAME_SHORT,
    HEADER_NAME_WHITESPACE_HEADER,
    HEADER_NAME_WHITESPACE_TAG,
    HEADER_NAME_WHITESPACE_VAL_LONG,
    HEADER_NAME_WHITESPACE_VAL_SHORT,
    HEADER_VAL_BASIC,
    HEADER_VAL_WHITESPACE_VAL_LONG,
    HEADER_VAL_WHITESPACE_VAL_SHORT,
    RESPONSE_PREFIX,
    TAG_COLON_LEADING,
    TAG_COLON_TRAILING,
    TAG_LONG,
    TAG_SHORT,
    TAG_WHITESPACE_HEADER,
    TAG_WHITESPACE_TAG,
    TAG_WHITESPACE_VAL_LONG,
    TAG_WHITESPACE_VAL_SHORT,
)
from utils import remote_config as rc
import json


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
    e.g, ' header ' in DD_TRACE_HEADER_TAGS=' header ' becomes 'header' and is expected to match req.header of 'header'
    """

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
    trimmed on mapping parts, but whitespaces in between non-whitespace chars are left in-tact.
    """

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
    but leading/trailing whitespace is stripped, using short form input
    """

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
    but leading/trailing whitespace is stripped, using long form input
    """

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
        rc.tracer_rc_state.reset().set_config(path, config).apply()
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
        rc.tracer_rc_state.reset().set_config(path, config).apply()
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
            pytest.fail(f"A span with /status in the resource name was not found {spans}")

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
            pytest.fail(f"A span with /status in the resource name was not found {spans}")

    def setup_tracing_client_http_header_tags_apm_multiconfig(self):
        """We need to test that when the APM_TRACING_MULTICONFIG capability is enabled, it
        takes the lowest priority.

        This follows the principle that the most specific config wins.
        """

        # Set a config with the wildcard service and env.
        path, config = self.get_rc_params(
            {
                "tracing_header_tags": [
                    {"header": "X-Test-Header", "tag_name": "test_header_rc"},
                    {"header": "X-Test-Header-2", "tag_name": "test_header_rc2"},
                    {"header": "Content-Length", "tag_name": ""},
                ]
            },
            service_name="*",
            env="*",
        )
        rc.tracer_rc_state.set_config(path, config).apply()
        self.req1 = weblog.get(
            "/status?code=202",
            headers={
                "X-Test-Header": "1",
                "X-Test-Header-2": "2",
                "Content-Length": "0",
                HEADER_NAME_SHORT: HEADER_VAL_BASIC,
            },
        )

        # Set a config with the weblog service and env.
        path, config = self.get_rc_params(
            {"tracing_header_tags": [{"header": "X-Test-Header", "tag_name": "test_header_rc_override"}]},
            service_name="weblog",
            env="system-tests",
        )
        rc.tracer_rc_state.set_config(path, config).apply()
        self.req2 = weblog.get(
            "/status?code=202",
            headers={
                "X-Test-Header": "1",
                "X-Test-Header-2": "2",
                "Content-Length": "0",
                HEADER_NAME_SHORT: HEADER_VAL_BASIC,
            },
        )

        # Delete the config with the weblog service and env. This should use the tracing_header_tags from the first
        # config.
        rc.tracer_rc_state.del_config(path)

        # Set a config with the weblog service and env.
        self.req3 = weblog.get(
            "/status?code=202",
            headers={
                "X-Test-Header": "1",
                "X-Test-Header-2": "2",
                "Content-Length": "0",
                HEADER_NAME_SHORT: HEADER_VAL_BASIC,
            },
        )

    def test_tracing_client_http_header_tags_apm_multiconfig(self):
        """Ensure the tracing http header tags can be set via RC with the APM_TRACING_MULTICONFIG capability."""
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
            pytest.fail(f"A span with /status in the resource name was not found {spans}")

        # Validate the spans generated by the second request
        spans = [span for _, _, span in interfaces.library.get_spans(request=self.req2, full_trace=True)]
        for s in spans:
            if "/status" in s["resource"]:
                # Headers tags set via remote config
                assert s["meta"].get(TAG_SHORT) == HEADER_VAL_BASIC
                assert s["meta"].get("test_header_rc_override")
                # Does not have headers set via remote config
                assert "test_header_rc2" not in s["meta"], s["meta"]
                assert "http.request.headers.content-length" in s["meta"], s["meta"]
                break
        else:
            pytest.fail(f"A span with /status in the resource name was not found {spans}")

        # Validate the spans generated by the third request. This should be identical to the first request, because
        # we deleted the config with the weblog service and env.
        spans = [span for _, _, span in interfaces.library.get_spans(request=self.req3, full_trace=True)]
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
            pytest.fail(f"A span with /status in the resource name was not found {spans}")

    def get_rc_params(self, header_tags: dict, service_name: str = "weblog", env: str = "system-tests"):
        config = {
            "action": "enable",
            "service_target": {"service": service_name, "env": env},
            "lib_config": header_tags,
        }
        rc_id = hash(json.dumps(config))
        return f"datadog/2/APM_TRACING/{rc_id}/config", config


@scenarios.tracing_config_nondefault
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Wildcard_Request_Headers:
    """Validates that the wildcard format for specifying headers correctly tags Request Headers"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_SHORT: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_SHORT: HEADER_VAL_BASIC}
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1

        span = spans[0]
        for tag in tags:
            assert tag in span.meta


@scenarios.tracing_config_nondefault
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Wildcard_Response_Headers:
    """Validates that the wildcard format for specifying headers correctly tags Response Headers"""

    def setup_trace_header_tags(self):
        self.r = weblog.get("/")

    def test_trace_header_tags(self):
        response_headers = self.r.headers
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1

        span = spans[0]
        span_meta = span.meta
        for key in response_headers:
            assert RESPONSE_PREFIX + key.lower() in span_meta
            assert span_meta[RESPONSE_PREFIX + key.lower()] == response_headers[key]


# The Datadog specific tracecontext flags to mark flags are set
TRACECONTEXT_FLAGS_SET = 1 << 31


class SpanLink:
    def __init__(self, data: dict, trace_id: str, trace_id_low: int, trace_id_high: int):
        self.data = data
        self.trace_id = trace_id
        self.trace_id_low = trace_id_low
        self.trace_id_high = trace_id_high

        self.attributes: dict[str, str] | None = data.get("attributes")
        self.trace_state: str | None = data.get("tracestate", data.get("trace_state"))
        self.flags: int = (data["flags"] | TRACECONTEXT_FLAGS_SET) if "flags" in data else 0

        if "span_id" in self.data:
            self.span_id = data["span_id"] if isinstance(data["span_id"], int) else int(data["span_id"], base=16)
        elif "spanID" in self.data:  # spanID is a string on base 10
            self.span_id = int(data["spanID"])
        else:
            raise ValueError(f"No span id exists in span link: {data}")

    @staticmethod
    def from_span_links(data: dict) -> "SpanLink":
        return SpanLink(
            data, trace_id=data["traceID"], trace_id_high=int(data["traceIDHigh"]), trace_id_low=int(data["traceID"])
        )

    @staticmethod
    def from_efficient_trace_payload_format(data: dict) -> "SpanLink":
        trace_id = data["traceID"]

        return SpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=(int(trace_id, 16) >> 64) & 0xFFFFFFFFFFFFFFFF,
            trace_id_low=int(trace_id, 16) & 0xFFFFFFFFFFFFFFFF,
        )

    @staticmethod
    def from_library_v1_span_links(data: dict) -> "SpanLink":
        # trace Id can be Go-style (int) and Java-style (hex string e.g. '0x...'). Encode int into java style
        trace_id: str = hex(data["trace_id"]) if isinstance(data["trace_id"], int) else data["trace_id"]

        if "trace_id_high" not in data:
            assert trace_id.startswith("0x")
            assert len(trace_id) > 18
            trace_id_high = int(trace_id[2:18], 16)  # 128-bit: high 64 bits (first 16 hex chars after 0x)
        else:
            trace_id_high = data["trace_id_high"]

        return SpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=trace_id_high,
            trace_id_low=int(trace_id, 16) & 0xFFFFFFFFFFFFFFFF,
        )

    @staticmethod
    def from_library_v1_attributes(data: dict) -> "SpanLink":
        trace_id = data["trace_id"]
        assert isinstance(trace_id, str)

        if "trace_id_high" not in data:
            assert trace_id.startswith("0x")
            assert len(trace_id) > 18
            trace_id_high = int(trace_id[2:18], 16)  # 128-bit: high 64 bits (first 16 hex chars after 0x)
        else:
            trace_id_high = data["trace_id_high"]

        return SpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=trace_id_high,
            trace_id_low=int(trace_id, 16) & 0xFFFFFFFFFFFFFFFF,
        )

    @staticmethod
    def from_legacy_format(data: dict) -> "SpanLink":
        trace_id = data["trace_id"]

        return SpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=int(trace_id[:16], base=16),
            trace_id_low=int(trace_id[-16:], base=16),
        )

    @staticmethod
    def from_library_legacy_format(data: dict) -> "SpanLink":
        # trace Id can be Go-style (int) and Java-style (hex string e.g. '0x...'). Encode int into java style
        trace_id: str = hex(data["trace_id"]) if isinstance(data["trace_id"], int) else data["trace_id"]

        return SpanLink(
            data,
            trace_id=trace_id,
            trace_id_high=int(trace_id[:16], base=16) if len(trace_id) > 16 else 0,
            trace_id_low=int(trace_id[-16:], base=16),
        )

    def __str__(self) -> str:
        return str(self.data)

    def __repr__(self) -> str:
        return repr(self.data)


def get_span_links(span: DataDogAgentSpan) -> list[SpanLink]:
    if span.get("spanLinks") is not None:
        logger.info("Span links are stored inside span.spanLinks")
        return [SpanLink.from_span_links(data) for data in span.get("spanLinks")]

    if span.trace.format == AgentTraceFormat.efficient_trace_payload_format and span.get("links") is not None:
        logger.info("Span links are stored inside span.links and trace format is v1")
        return [SpanLink.from_efficient_trace_payload_format(data) for data in span.get("links")]

    logger.info("Span links are stored inside span.meta['_dd.span_links'] and trace format is legacy")
    raw = span.meta.get("_dd.span_links", [])
    raw_deserilialized = json.loads(raw) if isinstance(raw, (str, bytes, bytearray)) else raw

    return [SpanLink.from_legacy_format(data) for data in raw_deserilialized]


@scenarios.default
@features.context_propagation_extract_behavior
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
                "baggage": "key1=value1",
            },
        )

    def test_single_tracecontext(self):
        interfaces.library.assert_trace_exists(self.r)
        traces = [trace for _, trace in interfaces.agent.get_traces(self.r)]
        trace_id = traces[0].trace_id_as_int
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert trace_id == 1
        assert span.get("parentID") == "1"
        span_links = get_span_links(span)
        assert len(span_links) == 0, "Expected span links to be absent"

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
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        traces = [trace for _, trace in interfaces.agent.get_traces(self.r)]
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"
        assert len(traces) > 0, "Agent received the incorrect amount of traces"

        # Test the extracted span context
        span = spans[0]
        trace_id = traces[0].trace_id_as_int
        assert trace_id == 2, traces[0].format
        assert span.get("parentID") == "2"

        # Test the extracted span links: One span link per conflicting trace context
        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        link = span_links[0]
        # Assert the W3C Trace Context (conflicting trace context) span link according to the format
        assert link.trace_id_low == 8687463697196027922, link  # int(0x7890123456789012)
        assert link.trace_id_high == 1311768467284833366, link  # int(0x1234567890123456)
        assert link.span_id == 1311768467284833366, link  # int (0x1234567890123456)
        assert link.attributes == {"reason": "terminated_context", "context_headers": "tracecontext"}

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] == "2"
        assert "_dd.p.tid=1111111111111111" in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]


@scenarios.tracing_config_nondefault
@features.context_propagation_extract_behavior
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
        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        # Assert the Datadog (restarted) span link
        link = span_links[0]
        assert link.trace_id_low == 1
        assert link.trace_id_high == 1229782938247303441
        assert link.span_id == 1
        assert link.attributes == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

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
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert (
            span.get("traceID") != "1"  # Lower 64-bits of traceparent
        )
        assert (
            span.get("traceID") != "8687463697196027922"  # Lower 64-bits of traceparent
        )
        assert span.get("parentID") is None

        # Test the extracted span links: One span link for the incoming (Datadog trace context).
        # In the case that span links are generated for conflicting trace contexts, those span links
        # are not included in the new trace context
        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        # Assert the Datadog (restarted) span link
        link = span_links[0]
        assert link.trace_id_low == 1
        assert link.trace_id_high == 1229782938247303441
        assert link.span_id == 1
        assert link.attributes == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]

    def setup_multiple_tracecontexts_with_overrides(self):
        self.r = weblog.get(
            "/make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-11111111111111110000000000000001-1234567890123456-01",
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts_with_overrides(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert (
            span.get("traceID") != "1"  # Lower 64-bits of traceparent
        )

        assert span.get("parentID") is None
        assert "tracestate" not in span

        # Test the extracted span links: One span link for the incoming (Datadog trace context).
        # In the case that span links are generated for conflicting trace contexts, those span links
        # are not included in the new trace context
        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        # Assert the Datadog (restarted) span link
        link = span_links[0]
        assert link.trace_id_low == 1
        assert link.trace_id_high == 1229782938247303441
        assert link.span_id == 1311768467284833366
        assert link.attributes == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]


@scenarios.tracing_config_nondefault
@features.context_propagation_extract_behavior
class Test_ExtractBehavior_Restart_Otel:
    """Same as Test_ExtractBehavior_Restart but the trace is started through the OTel extraction API.

    Covers the gap where restart span links were not attached when a trace was initiated via
    the OTel propagation API rather than the auto-instrumented HTTP path.
    """

    def _get_otel_span(self, spans: list) -> DataDogAgentSpan:
        """Return the span created by the OTel tracer (named otel_extract_distant_call)."""
        for span in spans:
            if span.get("resource") == "otel_extract_distant_call" or span.get("name") == "otel_extract_distant_call":
                return span
        # Fallback: return whichever span has span links
        for span in spans:
            if get_span_links(span):
                return span
        return spans[0]

    def setup_single_tracecontext(self):
        self.r = weblog.get(
            "/otel_drop_in_extract_and_make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-11111111111111110000000000000001-0000000000000001-01",
                "tracestate": "dd=s:2;t.dm:-4,foo=1",
                "baggage": "key1=value1",
            },
        )

    def test_single_tracecontext(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)

        span = self._get_otel_span(spans)
        assert span.get("traceID") != "1"
        assert span.get("parentID") is None

        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        link = span_links[0]
        assert link.trace_id_low == 1
        assert link.trace_id_high == 1229782938247303441
        assert link.span_id == 1
        assert link.attributes == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None
        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"].get("x-datadog-tags", "")
        assert "key1=value1" in data["request_headers"]["baggage"]

    def setup_multiple_tracecontexts(self):
        self.r = weblog.get(
            "/otel_drop_in_extract_and_make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-12345678901234567890123456789012-1234567890123456-01",
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)

        span = self._get_otel_span(spans)
        assert span.get("traceID") != "1"
        assert span.get("traceID") != "8687463697196027922"
        assert span.get("parentID") is None

        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        link = span_links[0]
        assert link.trace_id_low == 1
        assert link.trace_id_high == 1229782938247303441
        assert link.span_id == 1
        assert link.attributes == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None
        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"].get("x-datadog-tags", "")
        assert "key1=value1" in data["request_headers"]["baggage"]

    def setup_multiple_tracecontexts_with_overrides(self):
        self.r = weblog.get(
            "/otel_drop_in_extract_and_make_distant_call",
            params={"url": "http://weblog:7777/"},
            headers={
                "x-datadog-trace-id": "1",
                "x-datadog-parent-id": "1",
                "x-datadog-sampling-priority": "2",
                "x-datadog-tags": "_dd.p.tid=1111111111111111,_dd.p.dm=-4",
                "traceparent": "00-11111111111111110000000000000001-1234567890123456-01",
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts_with_overrides(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)

        span = self._get_otel_span(spans)
        assert span.get("traceID") != "1"
        assert span.get("parentID") is None

        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        link = span_links[0]
        assert link.trace_id_low == 1
        assert link.trace_id_high == 1229782938247303441
        assert link.span_id == 1311768467284833366
        assert link.attributes == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None
        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"].get("x-datadog-tags", "")
        assert "key1=value1" in data["request_headers"]["baggage"]


@scenarios.tracing_config_nondefault_2
@features.context_propagation_extract_behavior
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
        span_links = get_span_links(span)
        assert len(span_links) == 0, "Expected span links to be absent"

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
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the local span context
        span = spans[0]
        assert (
            span.get("traceID") != "1"  # Lower 64-bits of traceparent
        )
        assert (
            span.get("traceID") != "8687463697196027922"  # Lower 64-bits of traceparent
        )
        assert span.get("parentID") is None
        span_links = get_span_links(span)
        assert len(span_links) == 0, "Expected span links to be absent"

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "2"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "baggage" not in data["request_headers"]


@scenarios.tracing_config_nondefault_3
@features.context_propagation_extract_behavior
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
        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        # Assert the Datadog (restarted) span link
        link = span_links[0]
        assert link.trace_id_low == 1
        assert link.trace_id_high == 1229782938247303441, f"link: {link}"
        assert link.span_id == 1
        assert link.attributes == {"reason": "propagation_behavior_extract", "context_headers": "datadog"}

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
                "baggage": "key1=value1",
            },
        )

    def test_multiple_tracecontexts(self):
        interfaces.library.assert_trace_exists(self.r)
        spans = interfaces.agent.get_spans_list(self.r)
        assert len(spans) == 1, "Agent received the incorrect amount of spans"

        # Test the extracted span context
        span = spans[0]
        assert (
            span.get("traceID") != "1"  # Lower 64-bits of traceparent
        )
        assert (
            span.get("traceID") != "8687463697196027922"  # Lower 64-bits of traceparent
        )
        assert span.get("parentID") is None

        # Test the extracted span links: One span link for the incoming (Datadog trace context).
        # In the case that span links are generated for conflicting trace contexts, those span links
        # are not included in the new trace context
        span_links = get_span_links(span)
        assert len(span_links) == 1, "Expected span links to be present"

        # Assert the Datadog (restarted) span link
        link = span_links[0]
        assert link.trace_id_low == 1
        assert link.trace_id_high == 1229782938247303441
        assert link.span_id == 1

        # Test the next outbound span context
        assert self.r.status_code == 200
        data = json.loads(self.r.text)
        assert data is not None

        assert data["request_headers"]["x-datadog-trace-id"] != "1"
        assert "_dd.p.tid=1111111111111111" not in data["request_headers"]["x-datadog-tags"]
        assert "key1=value1" in data["request_headers"]["baggage"]
