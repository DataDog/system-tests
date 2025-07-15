# Copyright (c) 2018 W3C and contributors

# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

# 1. Redistributions of works must retain the original copyright notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the original copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
# 3. Neither the name of the W3C nor the names of its contributors may be used to endorse or promote products derived from this work without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import pytest

from utils.parametric.spec.tracecontext import get_tracecontext
from utils.parametric.spec.trace import find_span_in_traces, find_only_span
from utils import missing_feature, context, scenarios, features

parametrize = pytest.mark.parametrize


def temporary_enable_optin_tracecontext() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext",
    }
    return parametrize("library_env", [env])


def temporary_enable_optin_tracecontext_single_key() -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "tracecontext",
    }
    return parametrize("library_env", [env])


@scenarios.parametric
@features.datadog_headers_propagation
class Test_Headers_Tracecontext:
    @temporary_enable_optin_tracecontext()
    def test_both_traceparent_and_tracestate_missing(self, test_agent, test_library):
        """Harness sends a request without traceparent or tracestate
        expects a valid traceparent from the output header
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [])

    @temporary_enable_optin_tracecontext_single_key()
    @missing_feature(
        context.library == "ruby", reason="Propagators not configured for DD_TRACE_PROPAGATION_STYLE config"
    )
    def test_single_key_traceparent_included_tracestate_missing(self, test_agent, test_library):
        """Harness sends a request with traceparent but without tracestate
        expects a valid traceparent from the output header, with the same trace_id but different parent_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"]]
            )

        assert traceparent.trace_id == "12345678901234567890123456789012"
        assert traceparent.parent_id != "1234567890123456"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_included_tracestate_missing(self, test_agent, test_library):
        """Harness sends a request with traceparent but without tracestate
        expects a valid traceparent from the output header, with the same trace_id but different parent_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"]]
            )

        assert traceparent.trace_id == "12345678901234567890123456789012"
        assert traceparent.parent_id != "1234567890123456"

    @temporary_enable_optin_tracecontext()
    @missing_feature(context.library == "cpp", reason="the first observed traceparent is used")
    @missing_feature(
        context.library == "nodejs",
        reason="nodejs does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "php",
        reason="php does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "python",
        reason="python does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "golang",
        reason="golang does not reconcile duplicate http headers, if duplicate headers received the propagator will not be used",
    )
    @missing_feature(
        context.library == "ruby",
        reason="the tracer should reject the incoming traceparent(s) when there are multiple traceparent headers",
    )
    @missing_feature(
        context.library == "rust",
        reason="multi-value header extraction is not supported by otel rust yet",
    )
    def test_traceparent_duplicated(self, test_agent, test_library):
        """Harness sends a request with two traceparent headers
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, _ = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789011-1234567890123456-01"],
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                ],
            )

        assert traceparent.trace_id != "12345678901234567890123456789011"
        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_header_name(self, test_agent, test_library):
        """Harness sends an invalid traceparent using wrong names
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["trace-parent", "00-12345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["trace.parent", "00-12345678901234567890123456789012-1234567890123456-01"]]
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    @missing_feature(context.library == "ruby", reason="Ruby doesn't support case-insensitive distributed headers")
    def test_traceparent_header_name_valid_casing(self, test_agent, test_library):
        """Harness sends a valid traceparent using different combination of casing
        expects a valid traceparent from the output header
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["TraceParent", "00-12345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["TrAcEpArEnT", "00-12345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent3, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["TRACEPARENT", "00-12345678901234567890123456789012-1234567890123456-01"]]
            )

        assert traceparent1.trace_id == "12345678901234567890123456789012"
        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert traceparent3.trace_id == "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_0x00(self, test_agent, test_library):
        """Harness sends an invalid traceparent with extra trailing characters
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01."]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library,
                [
                    [
                        "traceparent",
                        "00-12345678901234567890123456789012-1234567890123456-01-what-the-future-will-be-like",
                    ],
                ],
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_0xcc(self, test_agent, test_library):
        """Harness sends an valid traceparent with future version 204 (0xcc)
        expects a valid traceparent from the output header with the same trace_id
        """
        with test_library:
            traceparent1, _ = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "cc-12345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent2, _ = make_single_request_and_get_tracecontext(
                test_library,
                [
                    [
                        "traceparent",
                        "cc-12345678901234567890123456789012-1234567890123456-01-what-the-future-will-be-like",
                    ],
                ],
            )

            traceparent3, _ = make_single_request_and_get_tracecontext(
                test_library,
                [
                    [
                        "traceparent",
                        "cc-12345678901234567890123456789012-1234567890123456-01.what-the-future-will-be-like",
                    ],
                ],
            )

        assert traceparent1.trace_id == "12345678901234567890123456789012"
        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert traceparent3.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_0xff(self, test_agent, test_library):
        """Harness sends an invalid traceparent with version 255 (0xff)
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "ff-12345678901234567890123456789012-1234567890123456-01"]]
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_illegal_characters(self, test_agent, test_library):
        """Harness sends an invalid traceparent with illegal characters in version
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", ".0-12345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "0.-12345678901234567890123456789012-1234567890123456-01"]]
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_too_long(self, test_agent, test_library):
        """Harness sends an invalid traceparent with version more than 2 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "000-12345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "0000-12345678901234567890123456789012-1234567890123456-01"]]
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_too_short(self, test_agent, test_library):
        """Harness sends an invalid traceparent with version less than 2 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "0-12345678901234567890123456789012-1234567890123456-01"]]
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_id_all_zero(self, test_agent, test_library):
        """Harness sends an invalid traceparent with trace_id = 00000000000000000000000000000000
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-00000000000000000000000000000000-1234567890123456-01"]]
            )

        assert traceparent.trace_id != "00000000000000000000000000000000"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_id_illegal_characters(self, test_agent, test_library):
        """Harness sends an invalid traceparent with illegal characters in trace_id
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-.2345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-1234567890123456789012345678901.-1234567890123456-01"]]
            )

        assert traceparent1.trace_id != ".2345678901234567890123456789012"
        assert traceparent2.trace_id != "1234567890123456789012345678901."

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_id_too_long(self, test_agent, test_library):
        """Harness sends an invalid traceparent with trace_id more than 32 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-123456789012345678901234567890123-1234567890123456-01"]]
            )

        assert traceparent.trace_id != "123456789012345678901234567890123"
        assert traceparent.trace_id != "12345678901234567890123456789012"
        assert traceparent.trace_id != "23456789012345678901234567890123"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_id_too_short(self, test_agent, test_library):
        """Harness sends an invalid traceparent with trace_id less than 32 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-1234567890123456789012345678901-1234567890123456-01"]]
            )

        assert traceparent.trace_id != "1234567890123456789012345678901"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_parent_id_all_zero(self, test_agent, test_library):
        """Harness sends an invalid traceparent with parent_id = 0000000000000000
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-0000000000000000-01"]]
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_parent_id_illegal_characters(self, test_agent, test_library):
        """Harness sends an invalid traceparent with illegal characters in parent_id
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-.234567890123456-01"]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-123456789012345.-01"]]
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_parent_id_too_long(self, test_agent, test_library):
        """Harness sends an invalid traceparent with parent_id more than 16 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-12345678901234567-01"]]
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_parent_id_too_short(self, test_agent, test_library):
        """Harness sends an invalid traceparent with parent_id less than 16 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-123456789012345-01"]]
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_flags_illegal_characters(self, test_agent, test_library):
        """Harness sends an invalid traceparent with illegal characters in trace_flags
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-.0"]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-0."]]
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_flags_too_long(self, test_agent, test_library):
        """Harness sends an invalid traceparent with trace_flags more than 2 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, _ = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-001"]]
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_flags_too_short(self, test_agent, test_library):
        """Harness sends an invalid traceparent with trace_flags less than 2 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-1"]]
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_ows_handling(self, test_agent, test_library):
        """Harness sends an valid traceparent with heading and trailing OWS
        expects a valid traceparent from the output header
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", " 00-12345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "\t00-12345678901234567890123456789012-1234567890123456-01"]]
            )

            traceparent3, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01 "]]
            )

            traceparent4, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01\t"]]
            )

            traceparent5, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "\t 00-12345678901234567890123456789012-1234567890123456-01 \t"]]
            )

        assert traceparent1.trace_id == "12345678901234567890123456789012"
        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert traceparent3.trace_id == "12345678901234567890123456789012"
        assert traceparent4.trace_id == "12345678901234567890123456789012"
        assert traceparent5.trace_id == "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_tracestate_included_traceparent_missing(self, test_agent, test_library):
        """Harness sends a request with tracestate but without traceparent
        expects a valid traceparent from the output header
        expects the tracestate to be discarded
        """
        with test_library:
            _, tracestate1 = make_single_request_and_get_tracecontext(test_library, [["tracestate", "foo=1"]])
            _, tracestate2 = make_single_request_and_get_tracecontext(test_library, [["tracestate", "foo=1,bar=2"]])

        # Updated the test to check that the number of tracestate list-members is the same,
        # since Datadog will add an entry.
        assert len(tracestate1.split(",")) == len(tracestate2.split(","))

    @temporary_enable_optin_tracecontext()
    def test_tracestate_included_traceparent_included(self, test_agent, test_library):
        """Harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1,bar=2"],
                ],
            )

        assert traceparent.trace_id == "12345678901234567890123456789012"
        assert tracestate["foo"] == "1"
        assert tracestate["bar"] == "2"

    @temporary_enable_optin_tracecontext()
    def test_tracestate_header_name(self, test_agent, test_library):
        """Harness sends an invalid tracestate using wrong names
        expects the tracestate to be discarded
        """
        with test_library:
            traceparent, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["trace-state", "foo=1"],
                ],
            )

            traceparent, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["trace.state", "foo=1"],
                ],
            )

        assert "foo" not in tracestate1
        assert "foo" not in tracestate2

    @temporary_enable_optin_tracecontext()
    @missing_feature(context.library == "ruby", reason="Ruby doesn't support case-insensitive distributed headers")
    def test_tracestate_header_name_valid_casing(self, test_agent, test_library):
        """Harness sends a valid tracestate using different combination of casing
        expects the tracestate to be inherited
        """
        with test_library:
            traceparent, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"], ["TraceState", "foo=1"]],
            )

            traceparent, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"], ["TrAcEsTaTe", "foo=1"]],
            )

            traceparent, tracestate3 = make_single_request_and_get_tracecontext(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"], ["TRACESTATE", "foo=1"]],
            )

        assert tracestate1["foo"] == "1"
        assert tracestate2["foo"] == "1"
        assert tracestate3["foo"] == "1"

    @temporary_enable_optin_tracecontext()
    @missing_feature(context.library == "cpp", reason="the first observed tracestate is used")
    @missing_feature(
        context.library == "nodejs",
        reason="nodejs does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "php",
        reason="php does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "golang",
        reason="golang does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "python",
        reason="python does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "rust",
        reason="multi-value header extraction is not supported by otel rust yet",
    )
    def test_tracestate_empty_header(self, test_agent, test_library):
        """Harness sends a request with empty tracestate header
        expects the empty tracestate to be discarded
        """
        with test_library:
            traceparent1, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"], ["tracestate", ""]],
            )

            traceparent2, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1"],
                    ["tracestate", ""],
                ],
            )

            traceparent3, tracestate3 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", ""],
                    ["tracestate", "foo=1"],
                ],
            )

        assert traceparent1.trace_id == "12345678901234567890123456789012"
        assert not tracestate1 or tracestate1 != ""

        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert tracestate2["foo"] == "1"

        assert traceparent3.trace_id == "12345678901234567890123456789012"
        assert tracestate3["foo"] == "1"

    @temporary_enable_optin_tracecontext()
    @missing_feature(context.library == "cpp", reason="the first observed tracestate is used")
    @missing_feature(
        context.library == "golang",
        reason="golang does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "nodejs",
        reason="nodejs does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "php",
        reason="php does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "python",
        reason="python does not reconcile duplicate http headers, if duplicate headers received one only one will be used",
    )
    @missing_feature(
        context.library == "rust",
        reason="multi-value header extraction is not supported by otel rust yet",
    )
    def test_tracestate_multiple_headers_different_keys(self, test_agent, test_library):
        """Harness sends a request with multiple tracestate headers, each contains different set of keys
        expects a combined tracestate
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1,bar=2"],
                    ["tracestate", "rojo=1,congo=2"],
                    ["tracestate", "baz=3"],
                ],
            )

        assert traceparent.trace_id == "12345678901234567890123456789012"
        assert "foo=1" in str(tracestate)
        assert "bar=2" in str(tracestate)
        assert "rojo=1" in str(tracestate)
        assert "congo=2" in str(tracestate)
        assert "baz=3" in str(tracestate)
        assert str(tracestate).index("foo=1") < str(tracestate).index("bar=2")
        assert str(tracestate).index("bar=2") < str(tracestate).index("rojo=1")
        assert str(tracestate).index("rojo=1") < str(tracestate).index("congo=2")
        assert str(tracestate).index("congo=2") < str(tracestate).index("baz=3")

    @temporary_enable_optin_tracecontext()
    def test_tracestate_duplicated_keys(self, test_agent, test_library):
        """Harness sends a request with an invalid tracestate header with duplicated keys
        expects the tracestate to be inherited, and the duplicated keys to be either kept as-is or one of them
        to be discarded
        """
        with test_library:
            traceparent1, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1,foo=1"],
                ],
            )

            traceparent2, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1,foo=2"],
                ],
            )

            traceparent3, tracestate3 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1"],
                    ["tracestate", "foo=1"],
                ],
            )

            traceparent4, tracestate4 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1"],
                    ["tracestate", "foo=2"],
                ],
            )

        assert traceparent1.trace_id == "12345678901234567890123456789012"
        assert "foo=1" in str(tracestate1)

        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert "foo=1" in str(tracestate2) or "foo=2" in str(tracestate2)

        assert traceparent3.trace_id == "12345678901234567890123456789012"
        assert "foo=1" in str(tracestate3)

        assert traceparent4.trace_id == "12345678901234567890123456789012"
        assert "foo=1" in str(tracestate4) or "foo=2" in str(tracestate4)

    @missing_feature(context.library < "python@2.7.0", reason="Not implemented")
    @missing_feature(context.library < "dotnet@2.51.0", reason="Not implemented")
    @missing_feature(context.library < "php@0.99.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.6.0", reason="Not implemented")
    @missing_feature(context.library < "java@1.35.0", reason="Not implemented")
    @missing_feature(context.library < "cpp@0.2.0", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.0.0", reason="Not implemented")
    @missing_feature(context.library < "golang@1.64.0", reason="Not implemented")
    def test_tracestate_w3c_p_extract(self, test_agent, test_library):
        """Ensure the last parent id tag is set according to the W3C Phase 2 spec"""
        with test_library:
            with test_library.dd_extract_headers_and_make_child_span(
                "p_set",
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "key1=value1,dd=s:2;o:rum;p:0123456789abcdef;t.dm:-4;t.usr.id:12345~"],
                ],
            ) as s1:
                pass

            with test_library.dd_extract_headers_and_make_child_span(
                "p_invalid",
                [
                    ["traceparent", "00-12345678901234567890123456789013-1234567890123457-01"],
                    ["tracestate", "key1=value1,dd=s:2;t.dm:-4;p:XX!X"],
                ],
            ) as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)

        assert len(traces) == 2
        case1, case2 = (
            find_span_in_traces(traces, s1.trace_id, s1.span_id),
            find_span_in_traces(traces, s2.trace_id, s2.span_id),
        )

        assert case1["name"] == "p_set"
        assert case1["meta"]["_dd.parent_id"] == "0123456789abcdef"

        assert case2["name"] == "p_invalid"
        assert case2["meta"]["_dd.parent_id"] == "XX!X"

    @missing_feature(context.library < "python@2.7.0", reason="Not implemented")
    @missing_feature(context.library < "dotnet@2.51.0", reason="Not implemented")
    @missing_feature(context.library < "php@0.99.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.6.0", reason="Not implemented")
    @missing_feature(context.library < "java@1.35.0", reason="Not implemented")
    @missing_feature(context.library < "cpp@0.2.0", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.0.0", reason="Not implemented")
    @missing_feature(context.library < "golang@1.64.0", reason="Not implemented")
    def test_tracestate_w3c_p_inject(self, test_agent, test_library):
        """Ensure the last parent id is propagated according to the W3C spec"""
        with test_library:
            with test_library.dd_start_span(name="new_span") as span:
                headers = test_library.dd_inject_headers(span.span_id)

            tracestate_headers = list(filter(lambda h: h[0].lower() == "tracestate", headers))
            assert len(tracestate_headers) == 1

            tracestate = tracestate_headers[0][1]
            # FIXME: nodejs paramerric app sets span.span_id to a string, convert this to an int
            assert f"p:{int(span.span_id):016x}" in tracestate

    @missing_feature(context.library < "python@2.7.0", reason="Not implemented")
    @missing_feature(context.library < "dotnet@2.51.0", reason="Not implemented")
    @missing_feature(context.library < "php@0.99.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.6.0", reason="Not implemented")
    @missing_feature(context.library < "java@1.50.0", reason="Not implemented")
    @missing_feature(context.library < "cpp@0.2.0", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.0.0", reason="Not implemented")
    @missing_feature(context.library < "golang@1.64.0", reason="Not implemented")
    def test_tracestate_w3c_p_extract_and_inject(self, test_agent, test_library):
        """Ensure the last parent id is propagated according to the W3C spec"""
        with test_library:
            with test_library.dd_extract_headers_and_make_child_span(
                "p_set",
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "key1=value1,dd=s:2;o:rum;p:0123456789abcdef;t.dm:-4;t.usr.id:12345~"],
                ],
            ) as s1:
                headers1 = test_library.dd_inject_headers(s1.span_id)

            with test_library.dd_extract_headers_and_make_child_span(
                "p_invalid",
                [
                    ["traceparent", "00-12345678901234567890123456789013-1234567890123457-01"],
                    ["tracestate", "key1=value1,dd=s:2;t.dm:-4;p:XX!X"],
                ],
            ) as s2:
                headers2 = test_library.dd_inject_headers(s2.span_id)

        traces = test_agent.wait_for_num_traces(2)

        assert len(traces) == 2
        case1, case2 = (
            find_span_in_traces(traces, s1.trace_id, s1.span_id),
            find_span_in_traces(traces, s2.trace_id, s2.span_id),
        )
        tracestate_headers1 = list(filter(lambda h: h[0].lower() == "tracestate", headers1))
        tracestate_headers2 = list(filter(lambda h: h[0].lower() == "tracestate", headers2))

        assert case1["name"] == "p_set"
        assert case1["meta"]["_dd.parent_id"] == "0123456789abcdef"

        assert len(tracestate_headers1) == 1
        tracestate1 = tracestate_headers1[0][1]
        # FIXME: nodejs paramerric app sets span.span_id to a string, convert this to an int
        assert f"p:{int(s1.span_id):016x}" in tracestate1

        assert case2["name"] == "p_invalid"
        assert case2["meta"]["_dd.parent_id"] == "XX!X"

        assert len(tracestate_headers2) == 1
        tracestate2 = tracestate_headers2[0][1]
        # FIXME: nodejs paramerric app sets span.span_id to a string, convert this to an int
        assert f"p:{int(s2.span_id):016x}" in tracestate2

    @missing_feature(context.library < "python@2.10.0", reason="Not implemented")
    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library < "php@0.99.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.6.0", reason="Not implemented")
    @missing_feature(context.library < "java@1.39.0", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.0.0", reason="Not implemented")
    @missing_feature(context.library < "golang@1.64.0", reason="Not implemented")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext"}])
    def test_tracestate_w3c_p_extract_datadog_w3c(self, test_agent, test_library):
        """Ensure the last parent id tag is set according to the W3C phase 3 spec"""
        with test_library:
            # 1) Trace ids and parent ids in datadog and tracecontext headers match
            with test_library.dd_extract_headers_and_make_child_span(
                "identical_trace_info",
                [
                    ["traceparent", "00-11111111111111110000000000000001-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;p:000000003ade68b1,foo=1"],
                    ["x-datadog-trace-id", "1"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                    ["x-datadog-parent-id", "987654321"],
                ],
            ) as s1:
                pass

            # 2) Trace ids in datadog and tracecontext headers do not match
            with test_library.dd_extract_headers_and_make_child_span(
                "trace_ids_do_not_match",
                [
                    ["traceparent", "00-11111111111111110000000000000002-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;p:000000000000000a,foo=1"],
                    ["x-datadog-parent-id", "10"],
                    ["x-datadog-trace-id", "2"],
                    ["x-datadog-tags", "_dd.p.tid=2222222222222222"],
                ],
            ) as s2:
                pass

            # 3) Parent ids in Datadog and tracecontext headers do not match
            with test_library.dd_extract_headers_and_make_child_span(
                "same_trace_non_matching_parent_ids",
                [
                    ["traceparent", "00-11111111111111110000000000000003-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;p:000000000000000a,foo=1"],
                    ["x-datadog-trace-id", "3"],
                    ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
                    ["x-datadog-parent-id", "10"],
                ],
            ) as s3:
                pass

            # 4) Parent ids do not match and p value is not present in tracestate
            with test_library.dd_extract_headers_and_make_child_span(
                "non_matching_span_missing_p_value",
                [
                    ["traceparent", "00-00000000000000000000000000000004-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2,foo=1"],
                    ["x-datadog-trace-id", "4"],
                    ["x-datadog-parent-id", "10"],
                ],
            ) as s4:
                pass

            with test_library.dd_extract_headers_and_make_child_span(
                "non_matching_span_non_matching_p_value",
                [
                    ["traceparent", "00-00000000000000000000000000000005-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;p:8fffffffffffffff,foo=1"],
                    ["x-datadog-parent-id", "10"],
                    ["x-datadog-trace-id", "5"],
                ],
            ) as s5:
                pass

        traces = test_agent.wait_for_num_traces(5)

        assert len(traces) == 5
        case1, case2, case3, case4, case5 = (
            find_span_in_traces(traces, s1.trace_id, s1.span_id),
            find_span_in_traces(traces, s2.trace_id, s2.span_id),
            find_span_in_traces(traces, s3.trace_id, s3.span_id),
            find_span_in_traces(traces, s4.trace_id, s4.span_id),
            find_span_in_traces(traces, s5.trace_id, s5.span_id),
        )

        # 1) Datadog and tracecontext headers, trace-id and span-id match
        # There is no need to propagate _dd.parent_id
        assert case1["name"] == "identical_trace_info"
        assert case1["parent_id"] == 987654321
        assert "_dd.parent_id" not in case1["meta"]

        # 2) trace-ids do not match
        # Datadog and tracecontext headers contain spans from different traces
        # We can not reparent the trace, datadog headers are used (future work - span link is used to track tracecontext span)
        assert case2["name"] == "trace_ids_do_not_match"
        assert case2["parent_id"] == 10
        assert "_dd.parent_id" not in case2["meta"]

        # 3) trace-id matches but parent ids do not
        # Ensure parent_id is extracted from tracecontext and last datadog parent id tag is set using the tracestate header
        assert case3["name"] == "same_trace_non_matching_parent_ids"
        assert case3["parent_id"] == 987654321
        assert case3["meta"]["_dd.parent_id"] == "000000000000000a"

        # 4) parent ids do not match and p value is not present in tracestate
        # Ensure parent_id is extracted from tracecontext and the last parent id tag is set using the datadog header
        assert case4["name"] == "non_matching_span_missing_p_value"
        assert case4["parent_id"] == 987654321
        assert case4["meta"]["_dd.parent_id"] == "000000000000000a"

        # 5) parent ids do not match and p value does not match datadog headers
        # Ensure parent_id is extracted from tracecontext and the last parent id tag is set using the tracestate header
        # Traceparent and tracestate headers are used as the source of truth, Datadog headers are ignored
        assert case5["name"] == "non_matching_span_non_matching_p_value"
        assert case5["parent_id"] == 987654321
        assert case5["meta"]["_dd.parent_id"] == "8fffffffffffffff"

    @pytest.mark.parametrize(
        "library_env",
        [{"DD_TRACE_PROPAGATION_EXTRACT_FIRST": "true", "DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext"}],
    )
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @missing_feature(context.library == "php", reason="Not implemented")
    def test_tracestate_w3c_p_phase_3_extract_first(self, test_agent, test_library):
        """Ensure the last parent id tag is not set when only Datadog headers are extracted"""

        # 1) Datadog and tracecontext headers, parent ids do not match
        with test_library.dd_extract_headers_and_make_child_span(
            "same_trace_different_parent_ids",
            [
                ["traceparent", "00-11111111111111110000000000000001-000000000000000f-01"],
                ["tracestate", "dd=s:2;p:0123456789abcdef,foo=1"],
                ["x-datadog-trace-id", "1"],
                ["x-datadog-parent-id", "987654320"],
                ["x-datadog-tags", "_dd.p.tid=1111111111111111"],
            ],
        ):
            pass

        traces = test_agent.wait_for_num_traces(1)
        case1 = find_only_span(traces)

        # 1) trace-id and span-id extracted from datadog headers, last datadog parent id is ignored
        assert case1["name"] == "same_trace_different_parent_ids"
        assert case1["parent_id"] == 987654320
        assert "_dd.parent_id" not in case1["meta"]

    @missing_feature(context.library < "java@1.36", reason="Not implemented")
    @pytest.mark.parametrize("library_env", [{"DD_TRACE_PROPAGATION_STYLE": "datadog,tracecontext"}])
    def test_tracestate_w3c_context_leak(self, test_agent, test_library):
        """Ensure high order bits do not leak between traces"""
        with test_library:
            with test_library.dd_extract_headers_and_make_child_span(
                "high_order_64_bits_set",
                [
                    ["traceparent", "00-33333333333333330000000000000003-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2;p:000000000000000a,foo=1"],
                    ["x-datadog-trace-id", "3"],
                    ["x-datadog-tags", "_dd.p.tid=3333333333333333"],
                    ["x-datadog-parent-id", "10"],
                ],
            ) as s1:
                pass

            with test_library.dd_extract_headers_and_make_child_span(
                "high_order_64_bits_unset",
                [
                    ["traceparent", "00-00000000000000000000000000000004-000000003ade68b1-01"],
                    ["tracestate", "dd=s:2,foo=1"],
                    ["x-datadog-trace-id", "4"],
                    ["x-datadog-parent-id", "10"],
                ],
            ) as s2:
                pass

        traces = test_agent.wait_for_num_traces(2)

        assert len(traces) == 2
        case1, case2 = (
            find_span_in_traces(traces, s1.trace_id, s1.span_id),
            find_span_in_traces(traces, s2.trace_id, s2.span_id),
        )

        assert case1["meta"].get("_dd.p.tid") == "3333333333333333"
        assert case2["meta"].get("_dd.p.tid") is None

    @temporary_enable_optin_tracecontext()
    def test_tracestate_all_allowed_characters(self, test_agent, test_library):
        """Harness sends a request with a valid tracestate header with all legal characters
        expects the tracestate to be inherited
        """
        key_without_vendor = "".join(
            ["".join(map(chr, range(0x61, 0x7A + 1))), "0123456789", "_", "-", "*", "/"]  # lcalpha  # DIGIT
        )
        key_with_vendor = key_without_vendor + "@a-z0-9_-*/"
        value = "".join(
            [
                "".join(map(chr, range(0x20, 0x2B + 1))),
                "".join(map(chr, range(0x2D, 0x3C + 1))),
                "".join(map(chr, range(0x3E, 0x7E + 1))),
            ]
        )

        with test_library:
            traceparent1, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", key_without_vendor + "=" + value],
                ],
            )

            traceparent2, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", key_with_vendor + "=" + value],
                ],
            )

        assert key_without_vendor in tracestate1
        assert tracestate1[key_without_vendor] == value

        assert key_with_vendor in tracestate2
        assert tracestate2[key_with_vendor] == value

    @temporary_enable_optin_tracecontext()
    @missing_feature(
        context.library == "php", reason="PHP may preserve whitespace of foreign vendors trracestate (allowed per spec)"
    )
    @missing_feature(
        context.library == "rust", reason="Invalid tracestate keys for OpenTelemetry's implementation"
    )
    def test_tracestate_ows_handling(self, test_agent, test_library):
        """Harness sends a request with a valid tracestate header with OWS
        expects the tracestate to be inherited
        """
        with test_library:
            traceparent1, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1 \t , \t bar=2, \t baz=3"],
                ],
            )

            traceparent2, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1\t \t,\t \tbar=2,\t \tbaz=3"],
                ],
            )

            traceparent3, tracestate3 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", " foo=1"],
                ],
            )

            traceparent4, tracestate4 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "\tfoo=1"],
                ],
            )

            traceparent5, tracestate5 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1 "],
                ],
            )

            traceparent6, tracestate6 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "foo=1\t"],
                ],
            )

            traceparent7, tracestate7 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00"],
                    ["tracestate", "\t foo=1 \t"],
                ],
            )

        assert tracestate1["foo"] == "1"
        assert tracestate1["bar"] == "2"
        assert tracestate1["baz"] == "3"

        assert tracestate2["foo"] == "1"
        assert tracestate2["bar"] == "2"
        assert tracestate2["baz"] == "3"

        assert traceparent3.trace_id == "12345678901234567890123456789012"
        assert tracestate3["foo"] == "1"

        assert traceparent4.trace_id == "12345678901234567890123456789012"
        assert tracestate4["foo"] == "1"

        assert traceparent5.trace_id == "12345678901234567890123456789012"
        assert tracestate5["foo"] == "1"

        assert traceparent6.trace_id == "12345678901234567890123456789012"
        assert tracestate6["foo"] == "1"

        assert traceparent7.trace_id == "12345678901234567890123456789012"
        assert tracestate7["foo"] == "1"

    # The following w3c test cases are skipped because we do not discard incoming tracestate headers during the context extraction:
    # - test_tracestate_key_illegal_characters
    # - test_tracestate_key_illegal_vendor_format
    # - test_tracestate_member_count_limit
    # - test_tracestate_key_length_limit
    # - test_tracestate_value_illegal_characters

    # The following AdvancedTest cases are skipped:
    # - test_multiple_requests_with_valid_traceparent
    # - test_multiple_requests_without_traceparent(self):
    # - test_multiple_requests_with_illegal_traceparent(self):


def make_single_request_and_get_tracecontext(test_library, headers_list):
    return get_tracecontext(test_library.dd_make_child_span_and_get_headers(headers_list))
