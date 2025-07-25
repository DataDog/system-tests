import pytest

from utils.parametric.spec.tracecontext import get_tracecontext
from utils import bug, missing_feature, context, scenarios, features

parametrize = pytest.mark.parametrize


def temporary_enable_propagationstyle_default() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext,Datadog",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext,Datadog",
    }
    return parametrize("library_env", [env])


@scenarios.parametric
@features.datadog_headers_propagation
class Test_Headers_Tracestate_DD:
    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_propagate_samplingpriority(self, test_agent, test_library):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        """
        with test_library:
            # 1) x-datadog-sampling-priority > 0
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "7890123456789012"],
                    ["x-datadog-parent-id", "1234567890123456"],
                    ["x-datadog-sampling-priority", "2"],
                ],
            )

            # 2) x-datadog-sampling-priority <= 0
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "7890123456789012"],
                    ["x-datadog-parent-id", "1234567890123456"],
                    ["x-datadog-sampling-priority", "-1"],
                ],
            )

            # 3) Sampled = 1, tracestate[dd][s] is not present
            headers3 = test_library.dd_make_child_span_and_get_headers(
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"]]
            )

            # 4) Sampled = 1, tracestate[dd][s] <= 0
            headers4 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=s:-1"],
                ],
            )

            # 5) Sampled = 1, tracestate[dd][s] > 0
            headers5 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=s:2"],
                ],
            )

            # 6) Sampled = 0, tracestate[dd][s] is not present
            headers6 = test_library.dd_make_child_span_and_get_headers(
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"]]
            )

            # 7) Sampled = 0, tracestate[dd][s] <= 0
            headers7 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1,dd=s:-1"],
                ],
            )

            # 8) Sampled = 0, tracestate[dd][s] > 0
            headers8 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1,dd=s:1"],
                ],
            )

        # 1) x-datadog-sampling-priority > 0
        # Result: SamplingPriority = headers['x-datadog-sampling-priority'], Sampled = 1
        assert headers1["x-datadog-sampling-priority"] == "2"

        traceparent1, tracestate1 = get_tracecontext(headers1)
        sampled1 = str(traceparent1).split("-")[3]
        dd_items1 = tracestate1["dd"].split(";")
        assert "traceparent" in headers1
        assert sampled1 == "01"
        assert "tracestate" in headers1
        assert "s:2" in dd_items1

        # 2) x-datadog-sampling-priority <= 0
        # Result: SamplingPriority = headers['x-datadog-sampling-priority'], Sampled = 0
        assert headers2["x-datadog-sampling-priority"] == "-1"

        traceparent2, tracestate2 = get_tracecontext(headers2)
        sampled2 = str(traceparent2).split("-")[3]
        dd_items2 = tracestate2["dd"].split(";")
        assert "traceparent" in headers2
        assert sampled2 == "00"
        assert "tracestate" in headers2
        assert "s:-1" in dd_items2

        # 3) Sampled = 1, tracestate[dd][s] is not present
        # Result: SamplingPriority = 1
        assert headers3["x-datadog-sampling-priority"] == "1"

        traceparent3, tracestate3 = get_tracecontext(headers3)
        sampled3 = str(traceparent3).split("-")[3]
        dd_items3 = tracestate3["dd"].split(";")
        assert "traceparent" in headers3
        assert sampled3 == "01"
        assert "tracestate" in headers3
        assert "s:1" in dd_items3 or not any(item.startswith("s:") for item in dd_items3)

        # 4) Sampled = 1, tracestate[dd][s] <= 0
        # Result: SamplingPriority = 1
        assert headers4["x-datadog-sampling-priority"] == "1"

        traceparent4, tracestate4 = get_tracecontext(headers4)
        sampled4 = str(traceparent4).split("-")[3]
        dd_items4 = tracestate4["dd"].split(";")
        assert "traceparent" in headers4
        assert sampled4 == "01"
        assert "tracestate" in headers4
        assert "s:1" in dd_items4 or not any(item.startswith("s:") for item in dd_items4)

        # 5) Sampled = 1, tracestate[dd][s] > 0
        # Result: SamplingPriority = incoming sampling priority
        assert headers5["x-datadog-sampling-priority"] == "2"

        traceparent5, tracestate5 = get_tracecontext(headers5)
        sampled5 = str(traceparent5).split("-")[3]
        dd_items5 = tracestate5["dd"].split(";")
        assert "traceparent" in headers5
        assert sampled5 == "01"
        assert "tracestate" in headers5
        assert "s:2" in dd_items5

        # 6) Sampled = 0, tracestate[dd][s] is not present
        # Result: SamplingPriority = 0
        assert headers6["x-datadog-sampling-priority"] == "0"

        traceparent6, tracestate6 = get_tracecontext(headers6)
        sampled6 = str(traceparent6).split("-")[3]
        assert "traceparent" in headers6
        assert sampled6 == "00"
        if "dd" in tracestate6:
            dd_items6 = tracestate6["dd"].split(";")
            assert "s:0" in dd_items6 or not any(item.startswith("s:") for item in dd_items6)

        # 7) Sampled = 0, tracestate[dd][s] <= 0
        # Result: SamplingPriority = incoming sampling priority
        assert headers7["x-datadog-sampling-priority"] == "-1"

        traceparent7, tracestate7 = get_tracecontext(headers7)
        sampled7 = str(traceparent7).split("-")[3]
        dd_items7 = tracestate7["dd"].split(";")
        assert "traceparent" in headers7
        assert sampled7 == "00"
        assert "tracestate" in headers7
        assert "s:-1" in dd_items7

        # 8) Sampled = 0, tracestate[dd][s] > 0
        # Result: SamplingPriority = 0
        assert headers8["x-datadog-sampling-priority"] == "0"

        traceparent8, tracestate8 = get_tracecontext(headers8)
        sampled8 = str(traceparent8).split("-")[3]
        assert "traceparent" in headers8
        assert sampled8 == "00"
        assert "tracestate" in headers8
        if "dd" in tracestate8:
            dd_items8 = tracestate8["dd"].split(";")
            assert "s:0" in dd_items8 or not any(item.startswith("s:") for item in dd_items8)

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_propagate_origin(self, test_agent, test_library):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        """
        with test_library:
            # 1) x-datadog-origin is a well-known value
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "7890123456789012"],
                    ["x-datadog-parent-id", "1234567890123456"],
                    ["x-datadog-origin", "synthetics-browser"],
                ],
            )

            # 2) x-datadog-origin is NOT a well-known value
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "7890123456789012"],
                    ["x-datadog-parent-id", "1234567890123456"],
                    ["x-datadog-origin", "tracing2.0"],
                ],
            )

            # 3) x-datadog-origin has invalid characters
            headers3 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "7890123456789012"],
                    ["x-datadog-parent-id", "1234567890123456"],
                    ["x-datadog-origin", "synthetics~;=web,z"],
                ],
            )

            # 4) tracestate[dd][o] is not present
            headers4 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=s:-1"],
                ],
            )

            # 5) tracestate[dd][o] is present and is a well-known value
            headers5 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=s:-1;o:synthetics-browser"],
                ],
            )

            # 6) tracestate[dd][o] is present and is NOT a well-known value
            headers6 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=s:-1;o:tracing2.0"],
                ],
            )

        # 1) x-datadog-origin is a well-known value
        # Result: Origin set to header value
        assert headers1["x-datadog-origin"] == "synthetics-browser"

        traceparent1, tracestate1 = get_tracecontext(headers1)
        dd_items1 = tracestate1["dd"].split(";")
        assert "traceparent" in headers1
        assert "tracestate" in headers1
        assert "o:synthetics-browser" in dd_items1

        # 2) x-datadog-origin is NOT a well-known value
        # Result: Origin set to header value
        assert headers2["x-datadog-origin"] == "tracing2.0"

        traceparent2, tracestate2 = get_tracecontext(headers2)
        dd_items2 = tracestate2["dd"].split(";")
        assert "traceparent" in headers2
        assert "tracestate" in headers2
        assert "o:tracing2.0" in dd_items2

        # 3) x-datadog-origin has invalid characters. Since tilde must be unescaped during extraction,
        # all invalid characters including '~', must be replaced with '_',
        # and after that '=' must be replaced with `~`
        # Result: Origin set to header value, where invalid characters replaced by '_'
        origin = headers3["x-datadog-origin"]
        # allow implementations to split origin at the first ','
        assert origin in ("synthetics~;=web,z", "synthetics~;=web")

        traceparent3, tracestate3 = get_tracecontext(headers3)
        dd_items3 = tracestate3["dd"].split(";")
        assert "traceparent" in headers3
        assert "tracestate" in headers3
        # allow implementations to split origin at the first ','
        assert "o:synthetics__~web_z" in dd_items3 or "o:synthetics__~web" in dd_items3

        # 4) tracestate[dd][o] is not present
        # Result: Origin is not set
        assert "x-datadog-origin" not in headers4

        traceparent4, tracestate4 = get_tracecontext(headers4)
        dd_items4 = tracestate4["dd"].split(";")
        assert "traceparent" in headers4
        assert "tracestate" in headers4
        assert not any(item.startswith("o:") for item in dd_items4)

        # 5) tracestate[dd][o] is present and is a well-known value
        # Result: Origin set to header value
        assert headers5["x-datadog-origin"] == "synthetics-browser"

        traceparent5, tracestate5 = get_tracecontext(headers5)
        dd_items5 = tracestate5["dd"].split(";")
        assert "traceparent" in headers5
        assert "tracestate" in headers5
        assert "o:synthetics-browser" in dd_items5

        # 6) tracestate[dd][o] is present and is NOT a well-known value
        # Result: Origin set to header value
        assert headers6["x-datadog-origin"] == "tracing2.0"

        traceparent6, tracestate6 = get_tracecontext(headers6)
        dd_items6 = tracestate6["dd"].split(";")
        assert "traceparent" in headers6
        assert "tracestate" in headers6
        assert "o:tracing2.0" in dd_items6

    @temporary_enable_propagationstyle_default()
    @missing_feature(
        context.library == "cpp", reason="_dd.p.dm is reset to DEFAULT because we made the sampling decision"
    )
    @missing_feature(
        context.library == "golang",
        reason="False Bug: header[3,6]: can't guarantee the order of strings in the tracestate since they came from the map. BUG: header[4,5]: w3cTraceID shouldn't be present",
    )
    @bug(context.library in ["python@2.7.2", "python@2.7.3"], reason="AIT-9945")
    @bug(context.library == "ruby", reason="APMAPI-812")
    @bug(context.library >= "php@1.11.0", reason="APMAPI-1539")
    def test_headers_tracestate_dd_propagate_propagatedtags(self, test_agent, test_library):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        """
        with test_library:
            # 1) x-datadog-tags is populated with well-known tags
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "7890123456789012"],
                    ["x-datadog-parent-id", "1234567890123456"],
                    ["x-datadog-tags", "_dd.p.dm=-4"],
                ],
            )

            # 2) x-datadog-tags is populated with well-known tags that require
            # substituting "=" characters with ":" characters
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "7890123456789012"],
                    ["x-datadog-parent-id", "1234567890123456"],
                    ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.usr.id=baz64=="],
                ],
            )

            # 3) x-datadog-tags is populated with both well-known tags and unrecognized tags
            headers3 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["x-datadog-trace-id", "7890123456789012"],
                    ["x-datadog-parent-id", "1234567890123456"],
                    ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.usr.id=baz64==,_dd.p.url=http://localhost"],
                ],
            )

            # 4) tracestate[dd] does not contain propagated tags
            headers4 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=s:-1"],
                ],
            )

        # 1) x-datadog-tags is populated with well-known propagated tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        assert headers1["x-datadog-tags"] == "_dd.p.dm=-4"

        traceparent1, tracestate1 = get_tracecontext(headers1)
        dd_items1 = tracestate1["dd"].split(";")
        assert "traceparent" in headers1
        assert "tracestate" in headers1
        assert "t.dm:-4" in dd_items1

        # 2) x-datadog-tags is populated with well-known tags that require
        #    substituting "=" characters with ":" characters
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":"
        assert headers2["x-datadog-tags"] == "_dd.p.dm=-4,_dd.p.usr.id=baz64=="

        traceparent2, tracestate2 = get_tracecontext(headers2)
        dd_items2 = tracestate2["dd"].split(";")
        assert "traceparent" in headers2
        assert "tracestate" in headers2
        assert "t.dm:-4" in dd_items2
        assert "t.usr.id:baz64~~" in dd_items2

        # 3) x-datadog-tags is populated with both well-known tags and unrecognized tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":"
        assert headers3["x-datadog-tags"] == "_dd.p.dm=-4,_dd.p.usr.id=baz64==,_dd.p.url=http://localhost"

        traceparent3, tracestate3 = get_tracecontext(headers3)
        dd_items3 = tracestate3["dd"].split(";")
        assert "traceparent" in headers3
        assert "tracestate" in headers3
        assert "t.dm:-4" in dd_items3
        assert "t.usr.id:baz64~~" in dd_items3
        assert "t.url:http://localhost" in dd_items3

        # 4) tracestate[dd] does not contain propagated tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":". Tags that may be added are:
        #         - _dd.p.dm
        traceparent4, tracestate4 = get_tracecontext(headers4)
        dd_items4 = tracestate4["dd"].split(";")
        assert "traceparent" in headers4

        if headers4.get("x-datadog-tags", "") == "":
            assert not any(item.startswith("t:") for item in dd_items4)
        else:
            assert "tracestate" in headers4
            for tag in headers4["x-datadog-tags"].split(","):
                index = tag.index("=")
                key = tag[:index]
                val = tag[index:]

                assert key.startswith("_dd.p.")

                # adding "t.tid" to "tracestate" header is redundant,
                # but if it is present, assert the value matches "_dd.p.tid".
                assert (key == "_dd.p.tid" and "t.tid" not in dd_items4) or (
                    "t." + key[6:] + val.replace("=", ":") in dd_items4
                )

    @temporary_enable_propagationstyle_default()
    @missing_feature(context.library == "cpp", reason="_dd.p.dm is never dropped")
    @missing_feature(
        context.library == "nodejs", reason="Issue: the decision maker is removed. Is that allowed behavior?"
    )
    @missing_feature(context.library == "python", reason="Issue: Does not drop dm")
    @missing_feature(context.library == "ruby", reason="Issue: does not escape '~' characters to '=' in _dd.p.usr.id")
    def test_headers_tracestate_dd_propagate_propagatedtags_change_sampling_same_dm(self, test_agent, test_library):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        expects the decision maker to be passed through as DEFAULT
        """
        with test_library:
            # 1) tracestate[dd] is populated with well-known propagated tags
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=s:0;t.dm:-0;t.usr.id:baz64~~"],
                ],
            )

            # 2) tracestate[dd][o] is populated with both well-known tags and unrecognized propagated tags
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1,dd=s:1;t.dm:-0;t.usr.id:baz64~~;t.url:http://localhost"],
                ],
            )

        # 1) tracestate[dd] is populated with well-known propagated tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":"
        #         and dm=-0 is kept as dm=-0
        assert headers1["x-datadog-sampling-priority"] == "1"
        dd_tags1 = headers1["x-datadog-tags"].split(",")
        assert "_dd.p.dm=-0" in dd_tags1
        assert "_dd.p.usr.id=baz64==" in dd_tags1

        traceparent1, tracestate1 = get_tracecontext(headers1)
        dd_items1 = tracestate1["dd"].split(";")
        assert "traceparent" in headers1
        assert "tracestate" in headers1
        assert "s:1" in dd_items1 or not any(item.startswith("s:") for item in dd_items1)
        assert "t.dm:-0" in dd_items1
        assert "t.usr.id:baz64~~" in dd_items1

        # 2) tracestate[dd][o] is populated with both well-known tags and unrecognized propagated tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":"
        #         and drop dm
        assert headers2["x-datadog-sampling-priority"] == "0"
        dd_tags2 = headers2["x-datadog-tags"].split(",")
        assert not any(item.startswith("_dd.p.dm:") for item in dd_tags2)
        assert "_dd.p.usr.id=baz64==" in dd_tags2
        assert "_dd.p.url=http://localhost" in dd_tags2

        traceparent2, tracestate2 = get_tracecontext(headers2)
        dd_items2 = tracestate2["dd"].split(";")
        assert "traceparent" in headers2
        assert "tracestate" in headers2
        assert "s:0" in dd_items2 or not any(item.startswith("s:") for item in dd_items2)
        assert not any(item.startswith("t.dm:") for item in dd_items2)
        assert "t.usr.id:baz64~~" in dd_items2
        assert "t.url:http://localhost" in dd_items2

    @temporary_enable_propagationstyle_default()
    @missing_feature(context.library == "cpp", reason="_dd.p.dm does not change when a sampling priority was extracted")
    @missing_feature(context.library == "nodejs", reason="Issue: Does not reset dm to DEFAULT")
    @missing_feature(context.library == "python", reason="Issue: Does not reset dm to DEFAULT")
    @missing_feature(context.library == "ruby", reason="Issue: Does not reset dm to DEFAULT")
    def test_headers_tracestate_dd_propagate_propagatedtags_change_sampling_reset_dm(self, test_agent, test_library):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        expects the decision maker to be reset to DEFAULT
        """
        with test_library:
            # 1) tracestate[dd] is populated with well-known propagated tags
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1,dd=s:-1;t.dm:-4;t.usr.id:baz64~~"],
                ],
            )

            # 2) tracestate[dd][o] is populated with both well-known tags and unrecognized propagated tags
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1,dd=s:2;t.dm:-4;t.usr.id:baz64~~;t.url:http://localhost"],
                ],
            )

        # 1) tracestate[dd] is populated with well-known propagated tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":"
        #         and dm=-4 is reset to dm=-0
        assert headers1["x-datadog-sampling-priority"] == "1"
        dd_tags1 = headers1["x-datadog-tags"].split(",")
        assert "_dd.p.dm=-0" in dd_tags1
        assert "_dd.p.usr.id=baz64==" in dd_tags1

        traceparent1, tracestate1 = get_tracecontext(headers1)
        dd_items1 = tracestate1["dd"].split(";")
        assert "traceparent" in headers1
        assert "tracestate" in headers1
        assert "s:1" in dd_items1 or not any(item.startswith("s:") for item in dd_items1)
        assert "t.dm:-0" in dd_items1
        assert "t.usr.id:baz64~~" in dd_items1

        # 2) tracestate[dd][o] is populated with both well-known tags and unrecognized propagated tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":"
        #         and drop dm
        assert headers2["x-datadog-sampling-priority"] == "0"
        dd_tags2 = headers2["x-datadog-tags"].split(",")
        assert not any(item.startswith("_dd.p.dm:") for item in dd_tags2)
        assert "_dd.p.usr.id=baz64==" in dd_tags2
        assert "_dd.p.url=http://localhost" in dd_tags2

        traceparent2, tracestate2 = get_tracecontext(headers2)
        dd_items2 = tracestate2["dd"].split(";")
        assert "traceparent" in headers2
        assert "tracestate" in headers2
        assert "s:0" in dd_items2 or not any(item.startswith("s:") for item in dd_items2)
        assert not any(item.startswith("t.dm:") for item in dd_items2)
        assert "t.usr.id:baz64~~" in dd_items2
        assert "t.url:http://localhost" in dd_items2

    @temporary_enable_propagationstyle_default()
    @bug(library="php", reason="APMAPI-916")
    def test_headers_tracestate_dd_keeps_32_or_fewer_list_members(self, test_agent, test_library):
        """Harness sends requests with both tracestate and traceparent.
        all items in the input tracestate are propagated because the resulting
        number of list-members in the tracestate is less than or equal to 32
        """
        with test_library:
            other_vendors = ",".join(f"key{i}=value{i}" for i in range(1, 32))

            # 1) Input: 32 list-members with 'dd' at the end of the tracestate string
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", other_vendors + ",dd=s:-1"],
                ],
            )

            # 2) Input: 32 list-members with 'dd' at the beginning of the tracestate string
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "dd=s:-1," + other_vendors],
                ],
            )

            # 3) Input: 31 list-members without 'dd' in the tracestate string
            headers3 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", other_vendors],
                ],
            )

            # 4) Input: No tracestate string
            headers4 = test_library.dd_make_child_span_and_get_headers(
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"]],
            )

        # 1) Input: 32 list-members with 'dd' at the end of the tracestate string
        _, tracestate1 = get_tracecontext(headers1)
        tracestate_1_string = str(tracestate1)
        assert "key31=value31" in tracestate_1_string
        assert tracestate_1_string.startswith("dd=")
        assert len(tracestate_1_string.split(",")) == 32

        # 2) Input: 32 list-members with 'dd' at the beginning of the tracestate string
        _, tracestate2 = get_tracecontext(headers2)
        tracestate_2_string = str(tracestate2)
        assert "key31=value31" in tracestate_2_string
        assert tracestate_2_string.startswith("dd=")
        assert len(tracestate_2_string.split(",")) == 32

        # 3) Input: 31 list-members without 'dd' in the tracestate string
        _, tracestate3 = get_tracecontext(headers3)
        tracestate_3_string = str(tracestate3)
        assert "key31=value31" in tracestate_3_string
        assert tracestate_3_string.startswith("dd=")
        assert len(tracestate_3_string.split(",")) == 32

        # 4) Input: No tracestate string
        _, tracestate4 = get_tracecontext(headers4)
        tracestate_4_string = str(tracestate4)
        assert tracestate_4_string.startswith("dd=")
        assert len(tracestate_4_string.split(",")) == 1

    @temporary_enable_propagationstyle_default()
    @missing_feature(context.library < "java@1.24.0", reason="Implemented in 1.24.0")
    @bug(library="cpp", reason="APMAPI-914")
    @bug(library="dotnet", reason="APMAPI-914")
    @bug(library="nodejs", reason="APMAPI-914")
    @bug(library="python", reason="APMAPI-914")
    @bug(library="php", reason="APMAPI-916")
    def test_headers_tracestate_dd_evicts_32_or_greater_list_members(self, test_agent, test_library):
        """Harness sends a request with both tracestate and traceparent.
        the last list-member in the input tracestate is removed from the output
        tracestate string because the maximum number of list-members is 32.
        """
        with test_library:
            other_vendors = ",".join(f"key{i}=value{i}" for i in range(1, 32))

            # 1) Input: 32 list-members without 'dd' in the tracestate string
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", other_vendors + ",key32=value32"],
                ],
            )

        # 1) Input: 32 list-members without 'dd' in the tracestate string
        _, tracestate1 = get_tracecontext(headers1)
        tracestate_1_string = str(tracestate1)
        assert len(tracestate_1_string.split(",")) == 32
        assert "key32=value32" not in tracestate_1_string
        assert tracestate_1_string.startswith("dd=")
