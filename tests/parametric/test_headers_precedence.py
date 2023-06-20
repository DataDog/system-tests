from typing import Any

import pytest

from utils.parametric.spec.tracecontext import get_tracecontext
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils import missing_feature, context, scenarios

parametrize = pytest.mark.parametrize


def enable_tracecontext() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "tracecontext",
    }
    return parametrize("library_env", [env])


def enable_datadog() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "Datadog",
    }
    return parametrize("library_env", [env])


def enable_datadog_tracecontext() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "Datadog,tracecontext",
    }
    return parametrize("library_env", [env])


@scenarios.parametric
class Test_Headers_Precedence:
    @missing_feature(context.library == "java", reason="Issue: tracecontext is not enabled by default")
    @missing_feature(context.library == "ruby", reason="Ruby doesn't support case-insensitive distributed headers")
    def test_headers_precedence_propagationstyle_default(self, test_agent, test_library):
        with test_library:
            # 1) No headers
            headers1 = make_single_request_and_get_inject_headers(test_library, [])

            # 2) Only tracecontext headers
            headers2 = make_single_request_and_get_inject_headers(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],]
            )

            # 3) Only tracecontext headers, includes existing tracestate
            headers3 = make_single_request_and_get_inject_headers(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"], ["tracestate", "foo=1"],],
            )

            # 4) Both tracecontext and Datadog headers
            headers4 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

            # 5) Only Datadog headers
            headers5 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

            # 6) Invalid tracecontext, valid Datadog headers
            headers6 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-0000000000000000-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

        # 1) No headers
        # Result: new Datadog span context
        assert "x-datadog-trace-id" in headers1
        assert "x-datadog-parent-id" in headers1
        assert "x-datadog-sampling-priority" in headers1

        # traceparent also injected, assert that they are equal to Datadog values
        traceparent1, tracestate1 = get_tracecontext(headers1)
        tracestate1Arr = str(tracestate1).split(",")
        assert "traceparent" in headers1
        assert int(traceparent1.trace_id, base=16) == int(headers1["x-datadog-trace-id"])
        assert int(traceparent1.parent_id, base=16) == int(headers1["x-datadog-parent-id"])
        assert "tracestate" in headers1
        assert len(tracestate1Arr) == 1 and tracestate1Arr[0].startswith("dd=")

        # 2) Only tracecontext headers
        # Result: traceparent used
        traceparent2, tracestate2 = get_tracecontext(headers2)
        tracestate2Arr = str(tracestate2).split(",")
        assert "traceparent" in headers2
        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert traceparent2.parent_id != "1234567890123456"
        assert "tracestate" in headers2
        assert len(tracestate2Arr) == 1 and tracestate2Arr[0].startswith("dd=")

        # Datadog also injected, assert that they are equal to traceparent values
        assert int(headers2["x-datadog-trace-id"]) == int(traceparent2.trace_id[16:], base=16)
        assert int(headers2["x-datadog-parent-id"]) == int(traceparent2.parent_id, base=16)
        assert "x-datadog-sampling-priority" in headers2

        # 3) Only tracecontext headers, includes existing tracestate
        # Result: traceparent used
        traceparent3, tracestate3 = get_tracecontext(headers3)
        tracestate3Arr = str(tracestate3).split(",")
        assert "traceparent" in headers3
        assert traceparent3.trace_id == "12345678901234567890123456789012"
        assert traceparent3.parent_id != "1234567890123456"
        assert "tracestate" in headers3
        assert len(tracestate3Arr) == 2 and tracestate3Arr[0].startswith("dd=") and tracestate3Arr[1] == "foo=1"

        # Datadog also injected, assert that they are equal to traceparent values
        assert int(headers3["x-datadog-trace-id"]) == int(traceparent3.trace_id[16:], base=16)
        assert int(headers3["x-datadog-parent-id"]) == int(traceparent3.parent_id, base=16)
        assert "x-datadog-sampling-priority" in headers3

        # 4) Both tracecontext and Datadog headers
        # Result: traceparent used
        traceparent4, tracestate4 = get_tracecontext(headers4)
        tracestate4Arr = str(tracestate4).split(",")
        assert "traceparent" in headers4
        assert traceparent4.trace_id == "12345678901234567890123456789012"
        assert traceparent4.parent_id != "1234567890123456"
        assert "tracestate" in headers4
        assert len(tracestate4Arr) == 2 and tracestate4Arr[0].startswith("dd=") and tracestate4Arr[1] == "foo=1"

        # Datadog also injected, assert that they are equal to traceparent values
        assert int(headers4["x-datadog-trace-id"]) == int(traceparent4.trace_id[16:], base=16)
        assert int(headers4["x-datadog-parent-id"]) == int(traceparent4.parent_id, base=16)
        assert headers4["x-datadog-sampling-priority"] != -2

        # 5) Only Datadog headers
        # Result: Datadog used
        assert headers5["x-datadog-trace-id"] == "123456789"
        assert headers5["x-datadog-parent-id"] != "987654321"
        assert headers5["x-datadog-sampling-priority"] == "-2"

        # traceparent also injected, assert that they are equal to Datadog values
        traceparent5, tracestate5 = get_tracecontext(headers5)
        tracestate5Arr = str(tracestate5).split(",")
        assert "traceparent" in headers5
        assert int(traceparent5.trace_id, base=16) == int(headers5["x-datadog-trace-id"])
        assert int(traceparent5.parent_id, base=16) == int(headers5["x-datadog-parent-id"])
        assert "tracestate" in headers5
        assert len(tracestate5Arr) == 1 and tracestate5Arr[0].startswith("dd=")

        # 6) Invalid tracecontext, valid Datadog headers
        # Result: Datadog used
        assert headers6["x-datadog-trace-id"] == "123456789"
        assert headers6["x-datadog-parent-id"] != "987654321"
        assert headers6["x-datadog-sampling-priority"] == "-2"

        # traceparent also injected, assert that they are equal to Datadog values
        traceparent6, tracestate6 = get_tracecontext(headers6)
        tracestate6Arr = str(tracestate6).split(",")
        assert "traceparent" in headers6
        assert int(traceparent6.trace_id, base=16) == int(headers6["x-datadog-trace-id"])
        assert int(traceparent6.parent_id, base=16) == int(headers6["x-datadog-parent-id"])
        assert "tracestate" in headers6
        assert len(tracestate6Arr) == 1 and tracestate6Arr[0].startswith("dd=")

    @enable_tracecontext()
    @missing_feature(context.library == "ruby", reason="Ruby doesn't support case-insensitive distributed headers")
    def test_headers_precedence_propagationstyle_tracecontext(self, test_agent, test_library):
        with test_library:
            # 1) No headers
            headers1 = make_single_request_and_get_inject_headers(test_library, [])

            # 2) Only tracecontext headers
            headers2 = make_single_request_and_get_inject_headers(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],]
            )

            # 3) Only tracecontext headers, includes existing tracestate
            headers3 = make_single_request_and_get_inject_headers(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"], ["tracestate", "foo=1"],],
            )

            # 4) Both tracecontext and Datadog headers
            headers4 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

            # 5) Only Datadog headers
            headers5 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

            # 6) Invalid tracecontext, valid Datadog headers
            headers6 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-0000000000000000-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

        # 1) No headers
        # Result: new Datadog span context, tracestate updated with `dd` key
        tracestate1Arr = headers1["tracestate"].split(",")
        assert "traceparent" in headers1
        assert "tracestate" in headers1
        assert len(tracestate1Arr) == 1 and tracestate1Arr[0].startswith("dd=")
        assert "x-datadog-trace-id" not in headers1
        assert "x-datadog-parent-id" not in headers1
        assert "x-datadog-sampling-priority" not in headers1

        # 2) Only tracecontext headers
        # Result: traceparent used, tracestate updated with `dd` key
        traceparent2, tracestate2 = get_tracecontext(headers2)
        tracestate2Arr = str(tracestate2).split(",")
        assert "traceparent" in headers2
        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert traceparent2.parent_id != "1234567890123456"
        assert "tracestate" in headers2
        assert len(tracestate2Arr) == 1 and tracestate2Arr[0].startswith("dd=")
        assert "x-datadog-trace-id" not in headers2
        assert "x-datadog-parent-id" not in headers2
        assert "x-datadog-sampling-priority" not in headers2

        # 3) Only tracecontext headers, includes existing tracestate
        # Result: traceparent used, tracestate updated with `dd` key
        traceparent3, tracestate3 = get_tracecontext(headers3)
        tracestate3Arr = str(tracestate3).split(",")
        assert "traceparent" in headers3
        assert traceparent3.trace_id == "12345678901234567890123456789012"
        assert traceparent3.parent_id != "1234567890123456"
        assert "tracestate" in headers3
        assert len(tracestate3Arr) == 2 and tracestate3Arr[0].startswith("dd=") and tracestate3Arr[1] == "foo=1"
        assert "x-datadog-trace-id" not in headers3
        assert "x-datadog-parent-id" not in headers3
        assert "x-datadog-sampling-priority" not in headers3

        # 4) Both tracecontext and Datadog headers
        # Result: traceparent used, tracestate updated with `dd` key
        traceparent4, tracestate4 = get_tracecontext(headers4)
        tracestate4Arr = str(tracestate4).split(",")
        assert "traceparent" in headers4
        assert traceparent4.trace_id == "12345678901234567890123456789012"
        assert traceparent4.parent_id != "1234567890123456"
        assert "tracestate" in headers4
        assert len(tracestate4Arr) == 2 and tracestate4Arr[0].startswith("dd=") and tracestate4Arr[1] == "foo=1"
        assert "x-datadog-trace-id" not in headers4
        assert "x-datadog-parent-id" not in headers4
        assert "x-datadog-sampling-priority" not in headers4

        # 5) Only Datadog headers
        # Result: new Datadog span context, tracestate updated with `dd` key
        tracestate5Arr = headers5["tracestate"].split(",")
        assert "traceparent" in headers5
        assert "tracestate" in headers5
        assert len(tracestate5Arr) == 1 and tracestate5Arr[0].startswith("dd=")
        assert "x-datadog-trace-id" not in headers5
        assert "x-datadog-parent-id" not in headers5
        assert "x-datadog-sampling-priority" not in headers5

        # 6) Invalid tracecontext, valid Datadog headers
        # Result: new Datadog span context, tracestate updated with `dd` key
        tracestate6Arr = headers6["tracestate"].split(",")
        assert "traceparent" in headers6
        assert "tracestate" in headers6
        assert len(tracestate6Arr) == 1 and tracestate6Arr[0].startswith("dd=")
        assert "x-datadog-trace-id" not in headers6
        assert "x-datadog-parent-id" not in headers6
        assert "x-datadog-sampling-priority" not in headers6

    @enable_datadog()
    def test_headers_precedence_propagationstyle_datadog(self, test_agent, test_library):
        with test_library:
            # 1) No headers
            headers1 = make_single_request_and_get_inject_headers(test_library, [])

            # 2) Only tracecontext headers
            headers2 = make_single_request_and_get_inject_headers(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],]
            )

            # 3) Only tracecontext headers, includes existing tracestate
            headers3 = make_single_request_and_get_inject_headers(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"], ["tracestate", "foo=1"],],
            )

            # 4) Both tracecontext and Datadog headers
            headers5 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

            # 5) Only Datadog headers
            headers4 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

            # 6) Invalid tracecontext, valid Datadog headers
            headers6 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-0000000000000000-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

        # 1) No headers
        # Result: new Datadog span context
        assert "traceparent" not in headers1
        assert "tracestate" not in headers1
        assert "x-datadog-trace-id" in headers1
        assert "x-datadog-parent-id" in headers1
        assert "x-datadog-sampling-priority" in headers1

        # 2) Only tracecontext headers
        # Result: new Datadog span context
        assert "traceparent" not in headers2
        assert "tracestate" not in headers2
        assert "x-datadog-trace-id" in headers2
        assert "x-datadog-parent-id" in headers2
        assert "x-datadog-sampling-priority" in headers2

        # 3) Only tracecontext headers, includes existing tracestate
        # Result: new Datadog span context
        assert "traceparent" not in headers3
        assert "tracestate" not in headers3
        assert "x-datadog-trace-id" in headers3
        assert "x-datadog-parent-id" in headers3
        assert "x-datadog-sampling-priority" in headers3

        # 4) Both tracecontext and Datadog headers
        # Result: Datadog used
        assert "traceparent" not in headers4
        assert "tracestate" not in headers4
        assert headers4["x-datadog-trace-id"] == "123456789"
        assert "x-datadog-parent-id" in headers4
        assert headers4["x-datadog-parent-id"] != "987654321"
        assert headers4["x-datadog-sampling-priority"] == "-2"

        # 5) Only Datadog headers
        # Result: Datadog used
        assert "traceparent" not in headers5
        assert "tracestate" not in headers5
        assert headers5["x-datadog-trace-id"] == "123456789"
        assert "x-datadog-parent-id" in headers5
        assert headers5["x-datadog-parent-id"] != "987654321"
        assert headers5["x-datadog-sampling-priority"] == "-2"

        # 6) Invalid tracecontext, valid Datadog headers
        # Result: Datadog used
        assert "traceparent" not in headers6
        assert "tracestate" not in headers6
        assert headers6["x-datadog-trace-id"] == "123456789"
        assert "x-datadog-parent-id" in headers6
        assert headers6["x-datadog-parent-id"] != "987654321"
        assert headers6["x-datadog-sampling-priority"] == "-2"

    @enable_datadog_tracecontext()
    @missing_feature(context.library == "php", reason="Legacy behaviour: Fixed order instead of order of definition")
    @missing_feature(
        context.library == "golang",
        reason="BUG: suite #4 is failing - if context is successfully retrieved from W3C propagator, datadog propagator is NOT.run, thus not retrieving / overwriting the headers",
    )
    @missing_feature(context.library == "ruby", "Ruby doesn't support case-insensitive distributed headers")
    def test_headers_precedence_propagationstyle_datadog_tracecontext(self, test_agent, test_library):
        with test_library:
            # 1) No headers
            headers1 = make_single_request_and_get_inject_headers(test_library, [])

            # 2) Only tracecontext headers
            headers2 = make_single_request_and_get_inject_headers(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],]
            )

            # 3) Only tracecontext headers, includes existing tracestate
            headers3 = make_single_request_and_get_inject_headers(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"], ["tracestate", "foo=1"],],
            )

            # 4) Both tracecontext and Datadog headers
            headers4 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

            # 5) Only Datadog headers
            headers5 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

            # 6) Invalid tracecontext, valid Datadog headers
            headers6 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-0000000000000000-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "123456789"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "-2"],
                ],
            )

        # 1) No headers
        # Result: new Datadog span context
        assert "x-datadog-trace-id" in headers1
        assert "x-datadog-parent-id" in headers1
        assert "x-datadog-sampling-priority" in headers1

        # traceparent also injected, assert that they are equal to Datadog values
        traceparent1, tracestate1 = get_tracecontext(headers1)
        tracestate1Arr = str(tracestate1).split(",")
        assert "traceparent" in headers1
        assert int(traceparent1.trace_id, base=16) == int(headers1["x-datadog-trace-id"])
        assert int(traceparent1.parent_id, base=16) == int(headers1["x-datadog-parent-id"])
        assert "tracestate" in headers1
        assert len(tracestate1Arr) == 1 and tracestate1Arr[0].startswith("dd=")

        # 2) Only tracecontext headers
        # Result: traceparent used
        traceparent2, tracestate2 = get_tracecontext(headers2)
        tracestate2Arr = str(tracestate2).split(",")
        assert "traceparent" in headers2
        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert traceparent2.parent_id != "1234567890123456"
        assert "tracestate" in headers2
        assert len(tracestate2Arr) == 1 and tracestate2Arr[0].startswith("dd=")

        # Datadog also injected, assert that they are equal to traceparent values
        assert int(headers2["x-datadog-trace-id"]) == int(traceparent2.trace_id[16:], base=16)
        assert int(headers2["x-datadog-parent-id"]) == int(traceparent2.parent_id, base=16)
        assert "x-datadog-sampling-priority" in headers2

        # 3) Only tracecontext headers, includes existing tracestate
        # Result: traceparent used
        traceparent3, tracestate3 = get_tracecontext(headers3)
        tracestate3Arr = str(tracestate3).split(",")
        assert "traceparent" in headers3
        assert traceparent3.trace_id == "12345678901234567890123456789012"
        assert traceparent3.parent_id != "1234567890123456"
        assert "tracestate" in headers3
        assert len(tracestate3Arr) == 2 and tracestate3Arr[0].startswith("dd=") and tracestate3Arr[1] == "foo=1"

        # Datadog also injected, assert that they are equal to traceparent values
        assert int(headers3["x-datadog-trace-id"]) == int(traceparent3.trace_id[16:], base=16)
        assert int(headers3["x-datadog-parent-id"]) == int(traceparent3.parent_id, base=16)
        assert "x-datadog-sampling-priority" in headers3

        # 4) Both tracecontext and Datadog headers
        # Result: Datadog used
        assert headers4["x-datadog-trace-id"] == "123456789"
        assert headers4["x-datadog-parent-id"] != "987654321"
        assert headers4["x-datadog-sampling-priority"] == "-2"

        # traceparent also injected, assert that they are equal to Datadog values
        traceparent4, tracestate4 = get_tracecontext(headers4)
        tracestate4Arr = str(tracestate4).split(",")
        assert "traceparent" in headers4
        assert int(traceparent4.trace_id, base=16) == int(headers4["x-datadog-trace-id"])
        assert int(traceparent4.parent_id, base=16) == int(headers4["x-datadog-parent-id"])
        assert "tracestate" in headers4
        assert len(tracestate4Arr) == 1 and tracestate4Arr[0].startswith("dd=")

        # 5) Only Datadog headers
        # Result: Datadog used
        assert headers5["x-datadog-trace-id"] == "123456789"
        assert headers5["x-datadog-parent-id"] != "987654321"
        assert headers5["x-datadog-sampling-priority"] == "-2"

        # traceparent also injected, assert that they are equal to Datadog values
        traceparent5, tracestate5 = get_tracecontext(headers5)
        tracestate5Arr = str(tracestate5).split(",")
        assert "traceparent" in headers5
        assert int(traceparent5.trace_id, base=16) == int(headers5["x-datadog-trace-id"])
        assert int(traceparent5.parent_id, base=16) == int(headers5["x-datadog-parent-id"])
        assert "tracestate" in headers5
        assert len(tracestate5Arr) == 1 and tracestate5Arr[0].startswith("dd=")

        # 6) Invalid tracecontext, valid Datadog headers
        # Result: Datadog used
        assert headers6["x-datadog-trace-id"] == "123456789"
        assert headers6["x-datadog-parent-id"] != "987654321"
        assert headers6["x-datadog-sampling-priority"] == "-2"

        # traceparent also injected, assert that they are equal to Datadog values
        traceparent6, tracestate6 = get_tracecontext(headers6)
        tracestate6Arr = str(tracestate6).split(",")
        assert "traceparent" in headers6
        assert int(traceparent6.trace_id, base=16) == int(headers6["x-datadog-trace-id"])
        assert int(traceparent6.parent_id, base=16) == int(headers6["x-datadog-parent-id"])
        assert "tracestate" in headers6
        assert len(tracestate6Arr) == 1 and tracestate6Arr[0].startswith("dd=")
