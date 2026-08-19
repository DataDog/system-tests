import pytest

from utils.docker_fixtures.spec.tracecontext import get_tracecontext
from utils import scenarios, features
from .conftest import APMLibrary

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
    def test_headers_tracestate_dd_propagate_samplingpriority(self, test_library: APMLibrary):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        """
        with test_library:
            # 1) x-datadog-sampling-priority > 0
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "7890123456789012"),
                    ("x-datadog-parent-id", "1234567890123456"),
                    ("x-datadog-sampling-priority", "2"),
                ],
            )

            # 2) x-datadog-sampling-priority <= 0
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "7890123456789012"),
                    ("x-datadog-parent-id", "1234567890123456"),
                    ("x-datadog-sampling-priority", "-1"),
                ],
            )

            # 3) Sampled = 1, tracestate[dd][s] is not present
            headers3 = test_library.dd_make_child_span_and_get_headers(
                [("traceparent", "00-12345678901234567890123456789012-1234567890123456-01")]
            )

            # 4) Sampled = 1, tracestate[dd][s] <= 0
            headers4 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:-1"),
                ],
            )

            # 5) Sampled = 1, tracestate[dd][s] > 0
            headers5 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:2"),
                ],
            )

            # 6) Sampled = 0, tracestate[dd][s] is not present
            headers6 = test_library.dd_make_child_span_and_get_headers(
                [("traceparent", "00-12345678901234567890123456789012-1234567890123456-00")]
            )

            # 7) Sampled = 0, tracestate[dd][s] <= 0
            headers7 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-00"),
                    ("tracestate", "foo=1,dd=s:-1"),
                ],
            )

            # 8) Sampled = 0, tracestate[dd][s] > 0
            headers8 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-00"),
                    ("tracestate", "foo=1,dd=s:1"),
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
    def test_headers_tracestate_dd_propagate_origin(self, test_library: APMLibrary):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        """
        with test_library:
            # 1) x-datadog-origin is a well-known value
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "7890123456789012"),
                    ("x-datadog-parent-id", "1234567890123456"),
                    ("x-datadog-origin", "synthetics-browser"),
                ],
            )

            # 2) x-datadog-origin is NOT a well-known value
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "7890123456789012"),
                    ("x-datadog-parent-id", "1234567890123456"),
                    ("x-datadog-origin", "tracing2.0"),
                ],
            )

            # 3) x-datadog-origin has invalid characters
            headers3 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "7890123456789012"),
                    ("x-datadog-parent-id", "1234567890123456"),
                    ("x-datadog-origin", "synthetics~;=web,z"),
                ],
            )

            # 4) tracestate[dd][o] is not present
            headers4 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:-1"),
                ],
            )

            # 5) tracestate[dd][o] is present and is a well-known value
            headers5 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:-1;o:synthetics-browser"),
                ],
            )

            # 6) tracestate[dd][o] is present and is NOT a well-known value
            headers6 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:-1;o:tracing2.0"),
                ],
            )

        # 1) x-datadog-origin is a well-known value
        # Result: Origin set to header value
        assert headers1["x-datadog-origin"] == "synthetics-browser"

        _, tracestate1 = get_tracecontext(headers1)
        dd_items1 = tracestate1["dd"].split(";")
        assert "traceparent" in headers1
        assert "tracestate" in headers1
        assert "o:synthetics-browser" in dd_items1

        # 2) x-datadog-origin is NOT a well-known value
        # Result: Origin set to header value
        assert headers2["x-datadog-origin"] == "tracing2.0"

        _, tracestate2 = get_tracecontext(headers2)
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

        _, tracestate3 = get_tracecontext(headers3)
        dd_items3 = tracestate3["dd"].split(";")
        assert "traceparent" in headers3
        assert "tracestate" in headers3
        # allow implementations to split origin at the first ','
        assert "o:synthetics__~web_z" in dd_items3 or "o:synthetics__~web" in dd_items3

        # 4) tracestate[dd][o] is not present
        # Result: Origin is not set
        assert "x-datadog-origin" not in headers4

        _, tracestate4 = get_tracecontext(headers4)
        dd_items4 = tracestate4["dd"].split(";")
        assert "traceparent" in headers4
        assert "tracestate" in headers4
        assert not any(item.startswith("o:") for item in dd_items4)

        # 5) tracestate[dd][o] is present and is a well-known value
        # Result: Origin set to header value
        assert headers5["x-datadog-origin"] == "synthetics-browser"

        _, tracestate5 = get_tracecontext(headers5)
        dd_items5 = tracestate5["dd"].split(";")
        assert "traceparent" in headers5
        assert "tracestate" in headers5
        assert "o:synthetics-browser" in dd_items5

        # 6) tracestate[dd][o] is present and is NOT a well-known value
        # Result: Origin set to header value
        assert headers6["x-datadog-origin"] == "tracing2.0"

        _, tracestate6 = get_tracecontext(headers6)
        dd_items6 = tracestate6["dd"].split(";")
        assert "traceparent" in headers6
        assert "tracestate" in headers6
        assert "o:tracing2.0" in dd_items6

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_propagate_propagatedtags(self, test_library: APMLibrary):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        """
        with test_library:
            # 1) x-datadog-tags is populated with well-known tags
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "7890123456789012"),
                    ("x-datadog-parent-id", "1234567890123456"),
                    ("x-datadog-tags", "_dd.p.usr.id=MTIz"),
                ],
            )

            # 2) x-datadog-tags is populated with well-known tags that require
            # substituting "=" characters with ":" characters
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "7890123456789012"),
                    ("x-datadog-parent-id", "1234567890123456"),
                    ("x-datadog-tags", "_dd.p.dm=-4,_dd.p.usr.id=baz64=="),
                    ("x-datadog-sampling-priority", "1"),
                ],
            )

            # 3) x-datadog-tags is populated with both well-known tags and unrecognized tags
            headers3 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("x-datadog-trace-id", "7890123456789012"),
                    ("x-datadog-parent-id", "1234567890123456"),
                    ("x-datadog-tags", "_dd.p.dm=-4,_dd.p.usr.id=baz64==,_dd.p.url=http://localhost"),
                    ("x-datadog-sampling-priority", "1"),
                ],
            )

            # 4) tracestate[dd] does not contain propagated tags
            headers4 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:-1"),
                ],
            )

        # 1) x-datadog-tags is populated with well-known propagated tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        assert "_dd.p.usr.id=MTIz" in headers1["x-datadog-tags"]

        _, tracestate1 = get_tracecontext(headers1)
        dd_items1 = tracestate1["dd"].split(";")
        assert "traceparent" in headers1
        assert "tracestate" in headers1
        assert "t.usr.id:MTIz" in dd_items1

        # 2) x-datadog-tags is populated with well-known tags that require
        #    substituting "=" characters with ":" characters
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":"
        assert headers2["x-datadog-tags"] == "_dd.p.dm=-4,_dd.p.usr.id=baz64=="

        _, tracestate2 = get_tracecontext(headers2)
        dd_items2 = tracestate2["dd"].split(";")
        assert "traceparent" in headers2
        assert "tracestate" in headers2
        assert "t.dm:-4" in dd_items2
        assert "t.usr.id:baz64~~" in dd_items2

        # 3) x-datadog-tags is populated with both well-known tags and unrecognized tags
        # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
        #         and "=" is replaced with ":"
        assert headers3["x-datadog-tags"] == "_dd.p.dm=-4,_dd.p.usr.id=baz64==,_dd.p.url=http://localhost"

        _, tracestate3 = get_tracecontext(headers3)
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
        _, tracestate4 = get_tracecontext(headers4)
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
    def test_headers_tracestate_dd_propagate_propagatedtags_change_sampling_same_dm(self, test_library: APMLibrary):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        expects the decision maker to be passed through as DEFAULT
        """
        with test_library:
            # 1) tracestate[dd] is populated with well-known propagated tags
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:0;t.dm:-0;t.usr.id:baz64~~"),
                ],
            )

            # 2) tracestate[dd][o] is populated with both well-known tags and unrecognized propagated tags
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-00"),
                    ("tracestate", "foo=1,dd=s:1;t.dm:-0;t.usr.id:baz64~~;t.url:http://localhost"),
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

        _, tracestate1 = get_tracecontext(headers1)
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

        _, tracestate2 = get_tracecontext(headers2)
        dd_items2 = tracestate2["dd"].split(";")
        assert "traceparent" in headers2
        assert "tracestate" in headers2
        assert "s:0" in dd_items2 or not any(item.startswith("s:") for item in dd_items2)
        assert not any(item.startswith("t.dm:") for item in dd_items2)
        assert "t.usr.id:baz64~~" in dd_items2
        assert "t.url:http://localhost" in dd_items2

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_propagate_propagatedtags_change_sampling_reset_dm(self, test_library: APMLibrary):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        expects the decision maker to be reset to DEFAULT
        """
        with test_library:
            # 1) tracestate[dd] is populated with well-known propagated tags
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:-1;t.dm:-4;t.usr.id:baz64~~"),
                ],
            )

            # 2) tracestate[dd][o] is populated with both well-known tags and unrecognized propagated tags
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-00"),
                    ("tracestate", "foo=1,dd=s:2;t.dm:-4;t.usr.id:baz64~~;t.url:http://localhost"),
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

        _, tracestate1 = get_tracecontext(headers1)
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

        _, tracestate2 = get_tracecontext(headers2)
        dd_items2 = tracestate2["dd"].split(";")
        assert "traceparent" in headers2
        assert "tracestate" in headers2
        assert "s:0" in dd_items2 or not any(item.startswith("s:") for item in dd_items2)
        assert not any(item.startswith("t.dm:") for item in dd_items2)
        assert "t.usr.id:baz64~~" in dd_items2
        assert "t.url:http://localhost" in dd_items2

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_keeps_32_or_fewer_list_members(self, test_library: APMLibrary):
        """Harness sends requests with both tracestate and traceparent.
        all items in the input tracestate are propagated because the resulting
        number of list-members in the tracestate is less than or equal to 32
        """
        with test_library:
            other_vendors = ",".join(f"key{i}=value{i}" for i in range(1, 32))

            # 1) Input: 32 list-members with 'dd' at the end of the tracestate string
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", other_vendors + ",dd=s:-1"),
                ],
            )

            # 2) Input: 32 list-members with 'dd' at the beginning of the tracestate string
            headers2 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "dd=s:-1," + other_vendors),
                ],
            )

            # 3) Input: 31 list-members without 'dd' in the tracestate string
            headers3 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", other_vendors),
                ],
            )

            # 4) Input: No tracestate string
            headers4 = test_library.dd_make_child_span_and_get_headers(
                [("traceparent", "00-12345678901234567890123456789012-1234567890123456-01")],
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
    def test_headers_tracestate_dd_evicts_32_or_greater_list_members(self, test_library: APMLibrary):
        """Harness sends a request with both tracestate and traceparent.
        the last list-member in the input tracestate is removed from the output
        tracestate string because the maximum number of list-members is 32.
        """
        with test_library:
            other_vendors = ",".join(f"key{i}=value{i}" for i in range(1, 32))

            # 1) Input: 32 list-members without 'dd' in the tracestate string
            headers1 = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", other_vendors + ",key32=value32"),
                ],
            )

        # 1) Input: 32 list-members without 'dd' in the tracestate string
        _, tracestate1 = get_tracecontext(headers1)
        tracestate_1_string = str(tracestate1)
        assert len(tracestate_1_string.split(",")) == 32
        assert "key32=value32" not in tracestate_1_string
        assert tracestate_1_string.startswith("dd=")

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_trailing_semicolon_still_parses(self, test_library: APMLibrary):
        """EXPECT SUCCESS: a trailing ';' at the end of the 'dd' tracestate member value is a
        harmless, spec-permitted separator. It must NOT cause the whole 'dd' member - and the
        sampling priority/origin decoded from it - to be dropped. Contrast with the
        test_headers_tracestate_dd_*_fails_to_parse tests, where whitespace/empty elements
        appear *inside* (not trailing) the dd value and parsing of the whole dd member is
        expected to fail/be skipped instead.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:2;o:some;"),
                ],
            )

        # Expect: parsing succeeds - the trailing separator is ignored, s and o are still decoded
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        _, tracestate = get_tracecontext(headers)
        dd_items = tracestate["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_trailing_semicolon_and_ows_still_parses(self, test_library: APMLibrary):
        """EXPECT SUCCESS: a trailing ';' followed by OWS (space then tab) at the end of the
        'dd' tracestate member value is harmless and must not cause the whole 'dd' member to be
        dropped. See test_headers_tracestate_dd_trailing_semicolon_still_parses for context.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:2;o:some; \t"),
                ],
            )

        # Expect: parsing succeeds - the trailing separator and OWS are ignored, s and o are
        # still decoded
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        _, tracestate = get_tracecontext(headers)
        dd_items = tracestate["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_trailing_semicolon_ows_before_next_member_still_parses(
        self, test_library: APMLibrary
    ):
        """EXPECT SUCCESS: a trailing ';' followed by OWS, then the ',' that starts the next
        list-member, is harmless and must not cause the whole 'dd' member (nor the sibling
        list-member) to be dropped. See test_headers_tracestate_dd_trailing_semicolon_still_parses
        for context.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "dd=s:2;o:some;  ,x=y"),
                ],
            )

        # Expect: parsing succeeds - the trailing separator and OWS are ignored, s and o are
        # still decoded, and the sibling list-member 'x=y' is preserved
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        tracestate_str = str(get_tracecontext(headers)[1])
        assert "x=y" in tracestate_str.split(",")
        dd_items = get_tracecontext(headers)[1]["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_trailing_ows_without_semicolon_still_parses(self, test_library: APMLibrary):
        """EXPECT SUCCESS: trailing OWS (space then tab) at the end of the 'dd' tracestate
        member value, with no trailing ';' before it, is harmless padding and must not cause
        the whole 'dd' member to be dropped. See
        test_headers_tracestate_dd_trailing_semicolon_still_parses for context.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:2;o:some \t"),
                ],
            )

        # Expect: parsing succeeds - the trailing OWS is ignored, s and o are still decoded
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        _, tracestate = get_tracecontext(headers)
        dd_items = tracestate["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_trailing_ows_without_semicolon_before_next_member_still_parses(
        self, test_library: APMLibrary
    ):
        """EXPECT SUCCESS: trailing OWS (with no trailing ';' before it), followed by the ','
        that starts the next list-member, is harmless and must not cause the whole 'dd' member
        (nor the sibling list-member) to be dropped. See
        test_headers_tracestate_dd_trailing_semicolon_still_parses for context.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "dd=s:2;o:some  ,x=y"),
                ],
            )

        # Expect: parsing succeeds - the trailing OWS is ignored, s and o are still decoded,
        # and the sibling list-member 'x=y' is preserved
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        tracestate_str = str(get_tracecontext(headers)[1])
        assert "x=y" in tracestate_str.split(",")
        dd_items = get_tracecontext(headers)[1]["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_double_semicolon_still_parses(self, test_library: APMLibrary):
        """EXPECT SUCCESS: an empty submember caused by a duplicated ';' in the middle of the
        'dd' value is a harmless, spec-permitted empty list-item and must NOT cause the whole
        'dd' member to be dropped. See test_headers_tracestate_dd_trailing_semicolon_still_parses
        for context.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:2;;o:some"),
                ],
            )

        # Expect: parsing succeeds - the empty submember is ignored, s and o are still decoded
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        _, tracestate = get_tracecontext(headers)
        dd_items = tracestate["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_leading_semicolon_still_parses(self, test_library: APMLibrary):
        """EXPECT SUCCESS: a leading separator before the first 'dd' submember (an empty first
        element) is harmless, just like the double-';' case in
        test_headers_tracestate_dd_double_semicolon_still_parses, and must not cause the whole
        'dd' member to be dropped.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=;s:2;o:some"),
                ],
            )

        # Expect: parsing succeeds - the empty leading submember is ignored, s and o are still
        # decoded
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        _, tracestate = get_tracecontext(headers)
        dd_items = tracestate["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_interior_ows_between_submembers_fails_to_parse(self, test_library: APMLibrary):
        """EXPECT FAILURE/SKIP: unlike a harmless trailing separator (see
        test_headers_tracestate_dd_trailing_semicolon_still_parses), OWS *between* two 'dd'
        submembers (as opposed to trailing padding) makes the whole 'dd' value unparseable. In
        that case none of the sampling priority, origin, or tags decoded from 'dd' may be
        applied: parsing of the 'dd' member must be skipped entirely, falling back to the same
        behavior as when tracestate[dd] is simply absent.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:0;t.dm:934086a686-4;  t.x:y"),
                ],
            )

        # Expect: parsing of 'dd' is skipped - sampling priority falls back to the incoming
        # traceparent's sampled flag (here, 1) instead of the (unparsed) 's' value, origin is
        # not set, and none of the (would-be) decoded tags are propagated
        assert headers["x-datadog-sampling-priority"] == "1"
        assert "x-datadog-origin" not in headers

        _, tracestate = get_tracecontext(headers)
        dd_items = tracestate["dd"].split(";") if "dd" in tracestate else []
        assert "t.dm:934086a686-4" not in dd_items
        assert "t.x:y" not in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_dd_interior_ows_after_first_submember_fails_to_parse(self, test_library: APMLibrary):
        """EXPECT FAILURE/SKIP: OWS right after the first 'dd' submember (not trailing padding)
        makes the whole 'dd' value unparseable, just like OWS between later submembers in
        test_headers_tracestate_dd_interior_ows_between_submembers_fails_to_parse.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,dd=s:0; t.dm:934086a686-4"),
                ],
            )

        # Expect: parsing of 'dd' is skipped - sampling priority falls back to the incoming
        # traceparent's sampled flag (here, 1) instead of the (unparsed) 's' value, origin is
        # not set, and none of the (would-be) decoded tags are propagated
        assert headers["x-datadog-sampling-priority"] == "1"
        assert "x-datadog-origin" not in headers

        _, tracestate = get_tracecontext(headers)
        dd_items = tracestate["dd"].split(";") if "dd" in tracestate else []
        assert "t.dm:934086a686-4" not in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_outer_list_empty_member_between_commas_still_parses(self, test_library: APMLibrary):
        """EXPECT SUCCESS: per the W3C tracestate grammar (list-member = (key "=" value) / OWS),
        a list-member may be empty/OWS-only. A stray ',,' in the outer tracestate list (as
        opposed to inside the 'dd' value itself, see
        test_headers_tracestate_dd_double_semicolon_still_parses) produces such an empty
        list-member and must be skipped without affecting the surrounding list-members,
        including 'dd'.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1,,dd=s:2;o:some"),
                ],
            )

        # Expect: parsing succeeds - the empty outer list-member is ignored, s and o are still
        # decoded, and the sibling list-member 'foo=1' is preserved
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        tracestate_str = str(get_tracecontext(headers)[1])
        assert "foo=1" in tracestate_str.split(",")
        dd_items = get_tracecontext(headers)[1]["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items

    @temporary_enable_propagationstyle_default()
    def test_headers_tracestate_outer_list_ows_around_commas_still_parses(self, test_library: APMLibrary):
        """EXPECT SUCCESS: per the W3C tracestate grammar (tracestate = list-member 0*31( OWS
        "," OWS list-member )), OWS is explicitly permitted around the commas separating outer
        list-members. OWS surrounding the commas next to 'dd' - as distinct from OWS *inside*
        the 'dd' value, see test_headers_tracestate_dd_interior_ows_between_submembers_fails_to_parse -
        must not prevent 'dd' (or its neighbors) from being parsed.
        """
        with test_library:
            headers = test_library.dd_make_child_span_and_get_headers(
                [
                    ("traceparent", "00-12345678901234567890123456789012-1234567890123456-01"),
                    ("tracestate", "foo=1 , dd=s:2;o:some , bar=2"),
                ],
            )

        # Expect: parsing succeeds - the OWS around the outer commas is ignored, s and o are
        # still decoded, and both sibling list-members are preserved
        assert headers["x-datadog-sampling-priority"] == "2"
        assert headers["x-datadog-origin"] == "some"

        tracestate_str = str(get_tracecontext(headers)[1])
        tracestate_items = tracestate_str.split(",")
        assert "foo=1" in tracestate_items
        assert "bar=2" in tracestate_items
        dd_items = get_tracecontext(headers)[1]["dd"].split(";")
        assert "s:2" in dd_items
        assert "o:some" in dd_items
