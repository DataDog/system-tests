from typing import Any

import pytest

from utils.parametric.spec.tracecontext import get_tracecontext, TRACECONTEXT_FLAGS_SET
from utils.parametric.spec.trace import retrieve_span_links, find_span_in_traces
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils import bug, missing_feature, context, irrelevant, scenarios, features

parametrize = pytest.mark.parametrize


def enable_tracecontext() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext",
    }
    return parametrize("library_env", [env])


def enable_datadog() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "Datadog",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "Datadog",
    }
    return parametrize("library_env", [env])


def enable_datadog_tracecontext() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "Datadog,tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "Datadog,tracecontext",
    }
    return parametrize("library_env", [env])


def enable_tracecontext_datadog() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext,Datadog",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext,Datadog",
    }
    return parametrize("library_env", [env])


def enable_datadog_b3multi_tracecontext_extract_first_false() -> Any:
    env1 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "Datadog,b3multi,tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "Datadog,b3multi,tracecontext",
    }
    env2 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "Datadog,b3multi,tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "Datadog,b3multi,tracecontext",
        "DD_TRACE_PROPAGATION_EXTRACT_FIRST": "false",
    }
    return parametrize("library_env", [env1, env2])


def enable_datadog_b3multi_tracecontext_extract_first_true() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "Datadog,b3multi,tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "Datadog,b3multi,tracecontext",
        "DD_TRACE_PROPAGATION_EXTRACT_FIRST": "true",
    }
    return parametrize("library_env", [env])


def enable_tracecontext_datadog_b3multi_extract_first_false() -> Any:
    env1 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext,Datadog,b3multi",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext,Datadog,b3multi",
    }
    env2 = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext,Datadog,b3multi",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext,Datadog,b3multi",
        "DD_TRACE_PROPAGATION_EXTRACT_FIRST": "false",
    }
    return parametrize("library_env", [env1, env2])


def enable_tracecontext_datadog_b3multi_extract_first_true() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext,Datadog,b3multi",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext,Datadog,b3multi",
        "DD_TRACE_PROPAGATION_EXTRACT_FIRST": "true",
    }
    return parametrize("library_env", [env])


@scenarios.parametric
@features.datadog_headers_propagation
class Test_Headers_Precedence:
    @irrelevant(
        context.library >= "dotnet@2.22.0", reason="Newer versions include tracecontext as a default propagator"
    )
    @irrelevant(
        context.library >= "golang@1.47.0", reason="Newer versions include tracecontext as a default propagator"
    )
    @irrelevant(
        context.library >= "nodejs@3.14.0",
        reason="Newer versions include tracecontext as a default propagator (2.27.0 and 3.14.0)",
    )
    @irrelevant(context.library >= "php@0.84.0", reason="Newer versions include tracecontext as a default propagator")
    @irrelevant(context.library >= "python@1.7.0", reason="Newer versions include tracecontext as a default propagator")
    @irrelevant(context.library >= "cpp@0.1.12", reason="Implements the new 'datadog,tracecontext' default")
    @irrelevant(context.library >= "java@1.24.0", reason="Implements the new 'datadog,tracecontext' default")
    @irrelevant(context.library >= "ruby@1.17.0", reason="Implements the new 'datadog,tracecontext' default")
    def test_headers_precedence_propagationstyle_legacy(self, test_agent, test_library):
        self.test_headers_precedence_propagationstyle_datadog(test_agent, test_library)

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

        # traceparent not injected
        assert "traceparent" not in headers1
        assert "tracestate" not in headers1

        # 2) Only tracecontext headers
        # Result: new Datadog span context
        assert "x-datadog-trace-id" in headers2
        assert "x-datadog-parent-id" in headers2
        assert "x-datadog-sampling-priority" in headers2

        # traceparent not injected
        assert "traceparent" not in headers2
        assert "tracestate" not in headers2

        # 3) Only tracecontext headers, includes existing tracestate
        # Result: new Datadog span context
        assert "x-datadog-trace-id" in headers3
        assert "x-datadog-parent-id" in headers3
        assert "x-datadog-sampling-priority" in headers3

        # traceparent not injected
        assert "traceparent" not in headers3
        assert "tracestate" not in headers3

        # 4) Both tracecontext and Datadog headers
        # Result: use existing Datadog span context
        assert headers4["x-datadog-trace-id"] == "123456789"
        assert headers4["x-datadog-parent-id"] != "987654321"
        assert headers4["x-datadog-sampling-priority"] == "-2"

        # traceparent not injected
        assert "traceparent" not in headers4
        assert "tracestate" not in headers4

        # 5) Only Datadog headers
        # Result: use existing Datadog span context
        assert headers5["x-datadog-trace-id"] == "123456789"
        assert headers5["x-datadog-parent-id"] != "987654321"
        assert headers5["x-datadog-sampling-priority"] == "-2"

        # traceparent not injected
        assert "traceparent" not in headers5
        assert "tracestate" not in headers5

        # 6) Invalid tracecontext, valid Datadog headers
        # Result: use existing Datadog span context
        assert headers6["x-datadog-trace-id"] == "123456789"
        assert headers6["x-datadog-parent-id"] != "987654321"
        assert headers6["x-datadog-sampling-priority"] == "-2"

        # traceparent not injected
        assert "traceparent" not in headers6
        assert "tracestate" not in headers6

    @irrelevant(context.library >= "nodejs@5.0.0", reason="Default value was switched to datadog,tracecontext")
    @irrelevant(context.library >= "php@0.97.0", reason="Default value was switched to datadog,tracecontext")
    @irrelevant(context.library >= "python@2.6.0", reason="Default value was switched to datadog,tracecontext")
    @irrelevant(context.library >= "golang@1.61.0.dev", reason="Default value was switched to datadog,tracecontext")
    @irrelevant(context.library > "dotnet@2.47.0", reason="Default value was switched to datadog,tracecontext")
    @irrelevant(context.library == "cpp", reason="Issue: tracecontext,Datadog was never the default configuration")
    @irrelevant(context.library == "java", reason="Issue: tracecontext,Datadog was never the default configuration")
    @irrelevant(context.library == "ruby", reason="Issue: tracecontext,Datadog was never the default configuration")
    def test_headers_precedence_propagationstyle_default_tracecontext_datadog(self, test_agent, test_library):
        self.test_headers_precedence_propagationstyle_tracecontext_datadog(test_agent, test_library)

    @enable_tracecontext_datadog()
    def test_headers_precedence_propagationstyle_tracecontext_datadog(self, test_agent, test_library):
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
        assert int(traceparent1.trace_id[-16:], base=16) == int(headers1["x-datadog-trace-id"])
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

    @missing_feature(context.library < "java@1.24.0", reason="Implemented from 1.24.0")
    @missing_feature(context.library < "cpp@0.1.12", reason="Implemented in 0.1.12")
    @missing_feature(context.library < "dotnet@2.48.0", reason="Default value was updated in 2.48.0")
    @missing_feature(context.library < "python@2.6.0", reason="Default value was switched to datadog,tracecontext")
    @missing_feature(context.library < "golang@1.62.0", reason="Default value was updated in v1.62.0 (w3c phase 2)")
    @missing_feature(context.library < "nodejs@4.20.0", reason="Implemented in 4.20.0 (and 3.41.0)")
    @missing_feature(context.library < "php@0.98.0", reason="Default value was updated in v0.98.0 (w3c phase 2)")
    @missing_feature(context.library < "ruby@1.17.0", reason="Implemented from 1.17.0")
    def test_headers_precedence_propagationstyle_default_datadog_tracecontext(self, test_agent, test_library):
        self.test_headers_precedence_propagationstyle_datadog_tracecontext(test_agent, test_library)

    @enable_datadog_tracecontext()
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
        assert int(traceparent1.trace_id[-16:], base=16) == int(headers1["x-datadog-trace-id"])
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

    @missing_feature(context.library < "java@v1.43.0", reason="span links attributes field added in 1.43.0")
    @missing_feature(context.library == "ruby", reason="not_implemented yet")
    @missing_feature(context.library == "cpp", reason="not_implemented yet")
    @missing_feature(context.library == "dotnet", reason="not_implemented yet")
    @missing_feature(context.library == "golang", reason="not_implemented yet")
    @missing_feature(context.library == "nodejs", reason="not_implemented yet")
    @missing_feature(context.library == "php", reason="not_implemented yet")
    @enable_datadog_b3multi_tracecontext_extract_first_false()
    def test_headers_precedence_propagationstyle_resolves_conflicting_contexts(self, test_agent, test_library):
        """
        This test asserts that when multiple contexts are extracted,
        the first context extracted is the primary context, and the one used.
        If the latter contexts have a different trace_id than the primary context,
        they are added as span links to the resulting span.
        """
        with test_library:
            # 1) Datadog and tracecontext headers, Datadog is primary context,
            # trace-id does not match,
            # tracestate is present, so should be added to tracecontext span_link
            with test_library.extract_headers_and_make_child_span(
                name="span1",
                http_headers=[
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;t.tid:1111111111111111,foo=1"],
                    ["x-datadog-trace-id", "2"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                ],
            ) as s1:
                pass
            # 2) Datadog and tracecontext headers, trace-id does match, Datadog is primary context
            # we want to make sure there's no span link since they match
            with test_library.extract_headers_and_make_child_span(
                name="span2",
                http_headers=[
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;t.tid:1111111111111111,foo=1"],
                    ["x-datadog-trace-id", "1"],
                    ["x-datadog-parent-id", "987654322"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                ],
            ) as s2:
                pass
            # 3) Datadog, tracecontext, b3multi headers, Datadog is primary context
            # tracecontext and b3multi trace_id do match it
            # we should have two span links, b3multi should not have tracestate
            with test_library.extract_headers_and_make_child_span(
                name="span3",
                http_headers=[
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;t.tid:1111111111111111,foo=1"],
                    ["x-datadog-trace-id", "4"],
                    ["x-datadog-parent-id", "987654323"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                    ["x-b3-traceid", "11111111111111110000000000000003"],
                    ["x-b3-spanid", "a2fb4a1d1a96d312"],
                    ["x-b3-sampled", "1"],
                ],
            ) as s3:
                pass
            # 4) Datadog, b3multi headers edge case where we want to make sure NOT to create a span_link
            # if the secondary context has trace_id 0 since that's not valid.
            with test_library.extract_headers_and_make_child_span(
                name="span4",
                http_headers=[
                    ["x-datadog-trace-id", "5"],
                    ["x-datadog-parent-id", "987654324"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                    ["x-b3-traceid", "00000000000000000000000000000000"],
                    ["x-b3-spanid", "a2fb4a1d1a96d314"],
                    ["x-b3-sampled", "1"],
                ],
            ) as s4:
                pass
            # 5) Datadog, b3multi headers edge case where we want to make sure NOT to create a span_link
            # if the secondary context has span_id 0 since that's not valid.
            with test_library.extract_headers_and_make_child_span(
                name="span5",
                http_headers=[
                    ["x-datadog-trace-id", "6"],
                    ["x-datadog-parent-id", "987654325"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                    ["x-b3-traceid", "11111111111111110000000000000003"],
                    ["x-b3-spanid", " 0000000000000000"],
                    ["x-b3-sampled", "1"],
                ],
            ) as s5:
                pass

        traces = test_agent.wait_for_num_traces(5)
        span1, span2, span3, span4, span5 = (
            find_span_in_traces(traces, s1.trace_id, s1.span_id),
            find_span_in_traces(traces, s2.trace_id, s2.span_id),
            find_span_in_traces(traces, s3.trace_id, s3.span_id),
            find_span_in_traces(traces, s4.trace_id, s4.span_id),
            find_span_in_traces(traces, s5.trace_id, s5.span_id),
        )

        # 1) Datadog and tracecontext headers, trace-id does not match, Datadog is primary context
        # tracestate is present, so should be added to tracecontext span_link
        assert span1["trace_id"] == 2
        links0 = retrieve_span_links(span1)
        assert len(links0) == 1
        link0 = links0[0]
        assert link0["trace_id"] == 1
        assert link0["span_id"] == 987654321
        assert link0["attributes"] == {"reason": "terminated_context", "context_headers": "tracecontext"}
        assert link0["tracestate"] == "dd=s:2;t.tid:1111111111111111,foo=1"
        assert link0["trace_id_high"] == 1229782938247303441

        # 2) Datadog and tracecontext headers, trace-id does match, Datadog is primary context
        # we just want to make sure there's not span link since they match
        assert span2["trace_id"] == 1
        assert retrieve_span_links(span2) == None

        # 3) Datadog, tracecontext, b3multi headers, Datadog is primary context
        # tracecontext and b3multi headers do not match
        # we should have two span links, b3multi should not have tracestate
        assert span3["trace_id"] == 4
        links2 = retrieve_span_links(span3)
        assert len(links2) == 2
        link1 = links2[0]
        assert link1["trace_id"] == 3
        assert link1["span_id"] == 11744061942159299346
        assert link1["attributes"] == {"reason": "terminated_context", "context_headers": "b3multi"}
        assert link1["trace_id_high"] == 1229782938247303441

        link2 = links2[1]
        assert link2["trace_id"] == 1
        assert link2["span_id"] == 987654321
        assert link2["attributes"] == {"reason": "terminated_context", "context_headers": "tracecontext"}
        assert link2["tracestate"] == "dd=s:2;t.tid:1111111111111111,foo=1"
        assert link2["trace_id_high"] == 1229782938247303441

        # 4) Datadog, b3multi headers edge case where we want to make sure NOT to create a span_link
        # if the secondary context has trace_id 0 since that's not valid.
        assert span4["trace_id"] == 5
        assert span4.get("span_links") == None

        # 5) Datadog, b3multi headers edge case where we want to make sure NOT to create a span_link
        # if the secondary context has span_id 0 since that's not valid.
        assert span5["trace_id"] == 6
        assert span5.get("span_links") == None

    @missing_feature(context.library < "java@v1.43.0", reason="span links attributes field added in 1.43.0")
    @missing_feature(context.library == "ruby", reason="not_implemented yet")
    @missing_feature(context.library == "cpp", reason="not_implemented yet")
    @missing_feature(context.library == "dotnet", reason="not_implemented yet")
    @missing_feature(context.library == "golang", reason="not_implemented yet")
    @missing_feature(context.library == "nodejs", reason="not_implemented yet")
    @missing_feature(context.library == "php", reason="not_implemented yet")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext,datadog,b3multi"}])
    def test_headers_precedence_propagationstyle_resolves_conflicting_contexts_tracecontext_precedence(
        self, test_agent, test_library
    ):
        """
        This test is the same as above, but tests the precedence of tracecontext over datadog and b3multi
        """
        with test_library:
            # Trace ids with the three styles do not match
            with test_library.extract_headers_and_make_child_span(
                name="trace_ids_do_not_match",
                http_headers=[
                    ["traceparent", "00-11111111111111110000000000000002-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;p:000000000000000a,foo=1"],
                    ["x-datadog-parent-id", "10"],
                    ["x-datadog-trace-id", "2"],
                    ["x-datadog-tags", "_dd.p.tid=2222222222222222"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-b3-traceid", "11111111111111110000000000000003"],
                    ["x-b3-spanid", "a2fb4a1d1a96d312"],
                    ["x-b3-sampled", "0"],
                ],
            ) as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)

        assert span["name"] == "trace_ids_do_not_match"
        span_links = retrieve_span_links(span)
        assert len(span_links) == 2
        link1 = span_links[0]
        assert link1["trace_id"] == 2
        assert link1["span_id"] == 10
        assert link1["attributes"] == {"reason": "terminated_context", "context_headers": "datadog"}
        assert link1["trace_id_high"] == 2459565876494606882

        link2 = span_links[1]
        assert link2["trace_id"] == 3
        assert link2["span_id"] == 11744061942159299346
        assert link2["attributes"] == {"reason": "terminated_context", "context_headers": "b3multi"}
        assert link2["trace_id_high"] == 1229782938247303441

    # Checks for the consistent behavior of flags in span links.
    @irrelevant(context.library == "java", reason="implementation specs have not been determined")
    @irrelevant(context.library == "ruby", reason="implementation specs have not been determined")
    @irrelevant(context.library == "cpp", reason="implementation specs have not been determined")
    @irrelevant(context.library == "dotnet", reason="implementation specs have not been determined")
    @irrelevant(context.library == "golang", reason="implementation specs have not been determined")
    @irrelevant(context.library == "nodejs", reason="implementation specs have not been determined")
    @irrelevant(context.library == "php", reason="implementation specs have not been determined")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_PROPAGATION_STYLE": "tracecontext,datadog,b3multi"}])
    def test_headers_precedence_propagationstyle_resolves_conflicting_contexts_spanlinks_flags(
        self, test_agent, test_library
    ):
        """
        Ensure the flags and tracestate fields are properly set in the span links
        """
        with test_library:
            # Trace ids with the three styles do not match
            with test_library.extract_headers_and_make_child_span(
                name="trace_ids_do_not_match",
                http_headers=[
                    ["traceparent", "00-11111111111111110000000000000002-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;p:000000000000000a,foo=1"],
                    ["x-datadog-parent-id", "10"],
                    ["x-datadog-trace-id", "2"],
                    ["x-datadog-tags", "_dd.p.tid=2222222222222222"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-b3-traceid", "11111111111111110000000000000003"],
                    ["x-b3-spanid", "a2fb4a1d1a96d312"],
                    ["x-b3-sampled", "0"],
                ],
            ) as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)

        span_links = retrieve_span_links(span)
        assert len(span_links) == 2
        link1 = span_links[0]
        assert link1["flags"] == 1 | TRACECONTEXT_FLAGS_SET

        link2 = span_links[1]
        assert link2["flags"] == 0 | TRACECONTEXT_FLAGS_SET

    # Checks for the consistent behavior of omitting tracestate in span links.
    @missing_feature(context.library == "java", reason="not_implemented yet")
    @missing_feature(context.library == "ruby", reason="not_implemented yet")
    @missing_feature(context.library == "cpp", reason="not_implemented yet")
    @missing_feature(context.library == "dotnet", reason="not_implemented yet")
    @missing_feature(context.library == "golang", reason="not_implemented yet")
    @missing_feature(context.library == "nodejs", reason="not_implemented yet")
    @missing_feature(context.library == "php", reason="not_implemented yet")
    @enable_tracecontext_datadog()
    def test_headers_precedence_propagationstyle_resolves_conflicting_contexts_spanlinks_omit_tracestate(
        self, test_agent, test_library
    ):
        """
        Ensure the flags and tracestate fields are properly set in the span links
        """
        with test_library:
            # Trace ids with the three styles do not match
            with test_library.extract_headers_and_make_child_span(
                name="trace_ids_do_not_match",
                http_headers=[
                    ["traceparent", "00-11111111111111110000000000000002-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;p:000000000000000a,foo=1"],
                    ["x-datadog-parent-id", "10"],
                    ["x-datadog-trace-id", "2"],
                    ["x-datadog-tags", "_dd.p.tid=2222222222222222"],
                    ["x-datadog-sampling-priority", "2"],
                ],
            ) as s1:
                pass

        traces = test_agent.wait_for_num_traces(1)
        span = find_span_in_traces(traces, s1.trace_id, s1.span_id)

        span_links = retrieve_span_links(span)
        assert len(span_links) == 1
        link1 = span_links[0]
        assert link1.get("tracestate") == None

    @enable_datadog_b3multi_tracecontext_extract_first_false()
    @missing_feature(context.library < "cpp@0.1.12", reason="Implemented in 0.1.12")
    @missing_feature(context.library < "dotnet@2.42.0", reason="Implemented in 2.42.0")
    @missing_feature(context.library < "python@2.3.3", reason="Implemented in 2.3.3")
    @missing_feature(context.library < "java@1.24.0", reason="Implemented in 1.24.0")
    @missing_feature(context.library < "nodejs@4.20.0", reason="Implemented in 4.20.0 (and 3.41.0)")
    @missing_feature(context.library < "php@0.94.0", reason="Implemented in 0.94.0")
    @missing_feature(context.library < "ruby@1.17.0", reason="Implemented in 1.17.0")
    def test_headers_precedence_propagationstyle_tracecontext_last_extract_first_false_correctly_propagates_tracestate(
        self, test_agent, test_library
    ):
        self._test_headers_precedence_propagationstyle_includes_tracecontext_correctly_propagates_tracestate(
            test_agent, test_library, prefer_tracecontext=False, extract_first=False
        )

    @enable_datadog_b3multi_tracecontext_extract_first_true()
    @missing_feature(context.library == "cpp", reason="DD_TRACE_PROPAGATION_EXTRACT_FIRST is not yet implemented")
    @missing_feature(context.library == "php", reason="DD_TRACE_PROPAGATION_EXTRACT_FIRST is not yet implemented")
    @bug(
        context.library < "golang@1.57.0",
        reason="Legacy behaviour: tracecontext propagator would always take precedence",
    )
    def test_headers_precedence_propagationstyle_tracecontext_last_extract_first_true_correctly_propagates_tracestate(
        self, test_agent, test_library
    ):
        self._test_headers_precedence_propagationstyle_includes_tracecontext_correctly_propagates_tracestate(
            test_agent, test_library, prefer_tracecontext=False, extract_first=True
        )

    @enable_tracecontext_datadog_b3multi_extract_first_false()
    def test_headers_precedence_propagationstyle_tracecontext_first_extract_first_false_correctly_propagates_tracestate(
        self, test_agent, test_library
    ):
        self._test_headers_precedence_propagationstyle_includes_tracecontext_correctly_propagates_tracestate(
            test_agent, test_library, prefer_tracecontext=True, extract_first=False
        )

    @enable_tracecontext_datadog_b3multi_extract_first_true()
    def test_headers_precedence_propagationstyle_tracecontext_first_extract_first_true_correctly_propagates_tracestate(
        self, test_agent, test_library
    ):
        self._test_headers_precedence_propagationstyle_includes_tracecontext_correctly_propagates_tracestate(
            test_agent, test_library, prefer_tracecontext=True, extract_first=True
        )

    def _test_headers_precedence_propagationstyle_includes_tracecontext_correctly_propagates_tracestate(
        self, test_agent, test_library, prefer_tracecontext, extract_first
    ):
        """
        This test asserts that ALL the propagators are executed in the specified
        order, and the the first propagator to extract a valid trace context determines
        the trace-id, parent-id, and supplemental information such as
        x-datadog-sampling-priority, x-datadog-tags, tracestate, etc.

        However, one exception is this: If the tracecontext propagator is configured,
        even if it is not the first propagator to extract the trace context, the
        tracestate will be saved in the local trace context if the traceparent
        trace-id matches the extracted the trace-id.
        """
        with test_library:
            # 1) Datadog and tracecontext headers, trace-id and span-id match, tracestate is present
            # Note: This is expected to be the most frequent case
            headers1 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;t.tid:1111111111111111,foo=1"],
                    ["x-datadog-trace-id", "1"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                ],
            )
            # 2) Scenario 1 but the x-datadog-* headers don't match the tracestate string
            # Note: This is an exceptional case that should not happen, but we should be consistent
            headers2 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-11111111111111110000000000000002-000000003ade68b1-01"],
                    ["tracestate", "dd=s:1;t.tid:1111111111111111,foo=1"],
                    ["x-datadog-trace-id", "2"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                ],
            )

            # 3) Scenario 1 but there is no dd tracestate list-member
            # Note: This is an exceptional case that should not happen, but we should be consistent
            headers3 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-11111111111111110000000000000003-000000003ade68b1-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "3"],
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                ],
            )

            # 4) Datadog and tracecontext headers, trace-id is the same but span-id is different, tracestate is present
            # Note: This happens when a W3C Proxy / Cloud Provider continues the W3C trace
            headers4 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-11111111111111110000000000000004-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;t.tid:1111111111111111,foo=1"],
                    ["x-datadog-trace-id", "4"],
                    ["x-datadog-parent-id", "3540"],  # 3539 == 0xdd4
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                ],
            )

            # 5) Datadog and tracecontext headers, trace-id is different, tracestate is present
            # Note: This happens when a W3C Proxy / Cloud Provider starts a new W3C trace,
            # which would happen if the incoming request only had x-datadog-* headers
            headers5 = make_single_request_and_get_inject_headers(
                test_library,
                [
                    ["traceparent", "00-11111111111111110000000000000005-000000003ade68b1-01"],
                    ["tracestate", "foo=1"],
                    ["x-datadog-trace-id", "3541"],  # 3538 == 0xdd5
                    ["x-datadog-parent-id", "987654321"],
                    ["x-datadog-sampling-priority", "2"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                ],
            )

        traces = test_agent.wait_for_num_traces(num=5)

        # 1) Datadog and tracecontext headers, trace-id and span-id match, tracestate is present
        # Note: This is expected to be the most frequent case
        traceparent1, tracestate1 = get_tracecontext(headers1)
        assert traceparent1.trace_id == "11111111111111110000000000000001"
        if extract_first and not prefer_tracecontext:
            assert "foo" not in tracestate1
        else:
            assert tracestate1["foo"] == "1"

        # 2) Scenario 1 but the x-datadog-tags mismatch somehow
        # Note: This is an exceptional case that should not happen, but we should be consistent
        traceparent2, tracestate2 = get_tracecontext(headers2)
        assert traceparent2.trace_id == "11111111111111110000000000000002"
        if extract_first and not prefer_tracecontext:
            assert "foo" not in tracestate2
        else:
            assert tracestate2["foo"] == "1"

        if prefer_tracecontext:
            assert "s:2" not in tracestate2["dd"]
        else:
            assert "s:2" in tracestate2["dd"]

        # 3) Scenario 1 but there is no dd tracestate list-member
        # Note: This is an exceptional case that should not happen, but we should be consistent
        traceparent3, tracestate3 = get_tracecontext(headers3)
        assert traceparent3.trace_id == "11111111111111110000000000000003"
        if extract_first and not prefer_tracecontext:
            assert "foo" not in tracestate3
        else:
            assert tracestate3["foo"] == "1"

        if prefer_tracecontext:
            assert "s:2" not in tracestate3["dd"]
        else:
            assert "s:2" in tracestate3["dd"]

        # 4) Datadog and tracecontext headers, trace-id is the same but span-id is different, tracestate is present
        # Note: This happens when a W3C Proxy / Cloud Provider continues the W3C trace
        traceparent4, tracestate4 = get_tracecontext(headers4)
        assert traceparent4.trace_id == "11111111111111110000000000000004"
        if extract_first and not prefer_tracecontext:
            assert "foo" not in tracestate4
        else:
            assert tracestate4["foo"] == "1"

        # 5) Datadog and tracecontext headers, trace-id is different, tracestate is present
        # Note: This happens when a W3C Proxy / Cloud Provider starts a new W3C trace,
        # which would happen if the incoming request only had x-datadog-* headers
        traceparent5, tracestate5 = get_tracecontext(headers5)

        if prefer_tracecontext:
            assert traceparent5.trace_id == "11111111111111110000000000000005"
            assert tracestate5["foo"] == "1"
        else:
            assert traceparent5.trace_id == "11111111111111110000000000000dd5"
            assert "foo" not in tracestate5
