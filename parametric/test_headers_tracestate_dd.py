from typing import Any

import pytest

from parametric.spec.tracecontext import get_tracecontext
from parametric.utils.headers import make_single_request_and_get_inject_headers

parametrize = pytest.mark.parametrize


def temporary_enable_propagationstyle_default() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext,Datadog",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext,Datadog",
    }
    return parametrize("library_env", [env])


@temporary_enable_propagationstyle_default()
@pytest.mark.skip_library("dotnet", "Issue: We need to prefer the traceparent sampled flag to fix headers4 test case")
@pytest.mark.skip_library("java", "Issue: tracecontext is not available yet")
def test_headers_tracestate_dd_propagate_samplingpriority(test_agent, test_library):
    """
    harness sends a request with both tracestate and traceparent
    expects a valid traceparent from the output header with the same trace_id
    expects the tracestate to be inherited
    """
    with test_library:
        # 1) x-datadog-sampling-priority > 0
        headers1 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "7890123456789012"],
                ["x-datadog-parent-id", "1234567890123456"],
                ["x-datadog-sampling-priority", "2"],
            ],
        )

        # 2) x-datadog-sampling-priority <= 0
        headers2 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "7890123456789012"],
                ["x-datadog-parent-id", "1234567890123456"],
                ["x-datadog-sampling-priority", "-1"],
            ],
        )

        # 3) Sampled = 1, tracestate[dd][s] is not present
        headers3 = make_single_request_and_get_inject_headers(
            test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],]
        )

        # 4) Sampled = 1, tracestate[dd][s] <= 0
        headers4 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                ["tracestate", "foo=1,dd=s:-1"],
            ],
        )

        # 5) Sampled = 1, tracestate[dd][s] > 0
        headers5 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                ["tracestate", "foo=1,dd=s:2"],
            ],
        )

        # 6) Sampled = 0, tracestate[dd][s] is not present
        headers6 = make_single_request_and_get_inject_headers(
            test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],]
        )

        # 7) Sampled = 0, tracestate[dd][s] <= 0
        headers7 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                ["tracestate", "foo=1,dd=s:-1"],
            ],
        )

        # 8) Sampled = 0, tracestate[dd][s] > 0
        headers8 = make_single_request_and_get_inject_headers(
            test_library,
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
    assert "s:1" in dd_items3

    # 4) Sampled = 1, tracestate[dd][s] <= 0
    # Result: SamplingPriority = 1
    assert headers4["x-datadog-sampling-priority"] == "1"

    traceparent4, tracestate4 = get_tracecontext(headers4)
    sampled4 = str(traceparent4).split("-")[3]
    dd_items4 = tracestate4["dd"].split(";")
    assert "traceparent" in headers4
    assert sampled4 == "01"
    assert "tracestate" in headers4
    assert "s:1" in dd_items4

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
    dd_items6 = tracestate6["dd"].split(";")
    assert "traceparent" in headers6
    assert sampled6 == "00"
    assert "tracestate" in headers6
    assert "s:0" in dd_items6

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
    dd_items8 = tracestate8["dd"].split(";")
    assert "traceparent" in headers8
    assert sampled8 == "00"
    assert "tracestate" in headers8
    assert "s:0" in dd_items8


@temporary_enable_propagationstyle_default()
@pytest.mark.skip_library("dotnet", "The origin transformation has changed slightly")
@pytest.mark.skip_library("java", "Issue: tracecontext is not available yet")
def test_headers_tracestate_dd_propagate_origin(test_agent, test_library):
    """
    harness sends a request with both tracestate and traceparent
    expects a valid traceparent from the output header with the same trace_id
    expects the tracestate to be inherited
    """
    with test_library:
        # 1) x-datadog-origin is a well-known value
        headers1 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "7890123456789012"],
                ["x-datadog-parent-id", "1234567890123456"],
                ["x-datadog-origin", "synthetics-browser"],
            ],
        )

        # 2) x-datadog-origin is NOT a well-known value
        headers2 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "7890123456789012"],
                ["x-datadog-parent-id", "1234567890123456"],
                ["x-datadog-origin", "tracing2.0"],
            ],
        )

        # 3) x-datadog-origin has invalid characters
        headers3 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "7890123456789012"],
                ["x-datadog-parent-id", "1234567890123456"],
                ["x-datadog-origin", "synthetics~;=web,z"],
            ],
        )

        # 4) tracestate[dd][o] is not present
        headers4 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                ["tracestate", "foo=1,dd=s:-1"],
            ],
        )

        # 5) tracestate[dd][o] is present and is a well-known value
        headers5 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                ["tracestate", "foo=1,dd=s:-1;o:synthetics-browser"],
            ],
        )

        # 6) tracestate[dd][o] is present and is NOT a well-known value
        headers6 = make_single_request_and_get_inject_headers(
            test_library,
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
    assert origin == "synthetics~;=web,z" or origin == "synthetics~;=web"

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
@pytest.mark.skip_library("dotnet", "Issue: headers5 is not capturing t.dm")
@pytest.mark.skip_library(
    "golang",
    "False Bug: header[3,6]: can't guarantee the order of strings in the tracestate since they came from the map"
    "BUG: header[4,5]: w3cTraceID shouldn't be present",
)
@pytest.mark.skip_library("java", "Issue: tracecontext is not merged  yet, dm is reset on priority override")
def test_headers_tracestate_dd_propagate_propagatedtags(test_agent, test_library):
    """
    harness sends a request with both tracestate and traceparent
    expects a valid traceparent from the output header with the same trace_id
    expects the tracestate to be inherited
    """
    with test_library:
        # 1) x-datadog-tags is populated with well-known tags
        headers1 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "7890123456789012"],
                ["x-datadog-parent-id", "1234567890123456"],
                ["x-datadog-tags", "_dd.p.dm=-4"],
            ],
        )

        # 2) x-datadog-tags is populated with well-known tags that require
        # substituting "=" characters with ":" characters
        headers2 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "7890123456789012"],
                ["x-datadog-parent-id", "1234567890123456"],
                ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.usr.id=baz64=="],
            ],
        )

        # 3) x-datadog-tags is populated with both well-known tags and unrecognized tags
        headers3 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["x-datadog-trace-id", "7890123456789012"],
                ["x-datadog-parent-id", "1234567890123456"],
                ["x-datadog-tags", "_dd.p.dm=-4,_dd.p.usr.id=baz64==,_dd.p.url=http://localhost"],
            ],
        )

        # 4) tracestate[dd] does not contain propagated tags
        headers4 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                ["tracestate", "foo=1,dd=s:-1"],
            ],
        )

        # 5) tracestate[dd] is populated with well-known propagated tags
        headers5 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                ["tracestate", "foo=1,dd=s:-1;t.dm:-4;t.usr.id:baz64~~"],
            ],
        )

        # 6) tracestate[dd][o] is populated with both well-known tags and unrecognized propagated tags
        headers6 = make_single_request_and_get_inject_headers(
            test_library,
            [
                ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                ["tracestate", "foo=1,dd=s:-1;t.dm:-4;t.usr.id:baz64~~;t.url:http://localhost"],
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
            assert "t." + key[6:] + val.replace("=", ":") in dd_items4

    # 5) tracestate[dd] is populated with well-known propagated tags
    # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
    #         and "=" is replaced with ":"
    dd_tags5 = headers5["x-datadog-tags"].split(",")
    assert "_dd.p.dm=-4" in dd_tags5
    assert "_dd.p.usr.id=baz64==" in dd_tags5

    traceparent5, tracestate5 = get_tracecontext(headers5)
    dd_items5 = tracestate5["dd"].split(";")
    assert "traceparent" in headers5
    assert "tracestate" in headers5
    assert "t.dm:-4" in dd_items5
    assert "t.usr.id:baz64~~" in dd_items5

    # 6) tracestate[dd][o] is populated with both well-known tags and unrecognized propagated tags
    # Result: Tags are placed into the tracestate where "_dd.p." is replaced with "t."
    #         and "=" is replaced with ":"
    dd_tags6 = headers6["x-datadog-tags"].split(",")
    assert "_dd.p.dm=-4" in dd_tags6
    assert "_dd.p.usr.id=baz64==" in dd_tags6
    assert "_dd.p.url=http://localhost" in dd_tags6

    traceparent6, tracestate6 = get_tracecontext(headers6)
    dd_items6 = tracestate6["dd"].split(";")
    assert "traceparent" in headers6
    assert "tracestate" in headers6
    assert "t.dm:-4" in dd_items6
    assert "t.usr.id:baz64~~" in dd_items6
    assert "t.url:http://localhost" in dd_items6
