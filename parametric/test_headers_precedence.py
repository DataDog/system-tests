from typing import Any

import pytest

from parametric.spec.tracecontext import get_tracecontext
from parametric.utils.headers import make_single_request_and_get_headers

parametrize = pytest.mark.parametrize


def temporary_enable_propagationstyle_tracecontext() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext",
    }
    return parametrize("library_env", [env])


def temporary_enable_propagationstyle_datadog() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "Datadog",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "Datadog",
    }
    return parametrize("library_env", [env])


@pytest.mark.skip_library("dotnet", "tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_headers_precedence_propagationstyle_default(test_agent, test_library):
    with test_library:
        # 1) No headers
        headers1 = make_single_request_and_get_headers(test_library, [])

        # 2) Only tracecontext headers
        headers2 = make_single_request_and_get_headers(
            test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],]
        )

        # 3) Only tracecontext headers, includes existing tracestate
        headers3 = make_single_request_and_get_headers(
            test_library,
            [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"], ["tracestate", "foo=1"],],
        )

        # 4) Both tracecontext and Datadog headers
        headers4 = make_single_request_and_get_headers(
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
        headers5 = make_single_request_and_get_headers(
            test_library,
            [
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


@temporary_enable_propagationstyle_tracecontext()
@pytest.mark.skip_library("dotnet", "tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_headers_precedence_propagationstyle_tracecontext(test_agent, test_library):
    with test_library:
        # 1) No headers
        headers1 = make_single_request_and_get_headers(test_library, [])

        # 2) Only tracecontext headers
        headers2 = make_single_request_and_get_headers(
            test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],]
        )

        # 3) Only tracecontext headers, includes existing tracestate
        headers3 = make_single_request_and_get_headers(
            test_library,
            [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"], ["tracestate", "foo=1"],],
        )

        # 4) Both tracecontext and Datadog headers
        headers4 = make_single_request_and_get_headers(
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
        headers5 = make_single_request_and_get_headers(
            test_library,
            [
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


@temporary_enable_propagationstyle_datadog()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_headers_precedence_propagationstyle_datadog(test_agent, test_library):
    with test_library:
        # 1) No headers
        headers1 = make_single_request_and_get_headers(test_library, [])

        # 2) Only tracecontext headers
        headers2 = make_single_request_and_get_headers(
            test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],]
        )

        # 3) Only tracecontext headers, includes existing tracestate
        headers3 = make_single_request_and_get_headers(
            test_library,
            [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"], ["tracestate", "foo=1"],],
        )

        # 4) Both tracecontext and Datadog headers
        headers5 = make_single_request_and_get_headers(
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
        headers4 = make_single_request_and_get_headers(
            test_library,
            [
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
