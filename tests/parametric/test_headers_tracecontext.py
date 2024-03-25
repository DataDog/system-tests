# Copyright (c) 2018 W3C and contributors

# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

# 1. Redistributions of works must retain the original copyright notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the original copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
# 3. Neither the name of the W3C nor the names of its contributors may be used to endorse or promote products derived from this work without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from typing import Any

import pytest

from utils.parametric.spec.tracecontext import get_tracecontext
from utils.parametric.headers import make_single_request_and_get_inject_headers
from utils import missing_feature, context, scenarios, features

parametrize = pytest.mark.parametrize


def temporary_enable_optin_tracecontext() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext",
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext",
    }
    return parametrize("library_env", [env])


def temporary_enable_optin_tracecontext_single_key() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE": "tracecontext",
    }
    return parametrize("library_env", [env])


@scenarios.parametric
@features.datadog_headers_propagation
class Test_Headers_Tracecontext:
    @temporary_enable_optin_tracecontext()
    def test_both_traceparent_and_tracestate_missing(self, test_agent, test_library):
        """
        harness sends a request without traceparent or tracestate
        expects a valid traceparent from the output header
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [])

    @temporary_enable_optin_tracecontext_single_key()
    @missing_feature(
        context.library == "ruby", reason="Propagators not configured for DD_TRACE_PROPAGATION_STYLE config",
    )
    def test_single_key_traceparent_included_tracestate_missing(self, test_agent, test_library):
        """
        harness sends a request with traceparent but without tracestate
        expects a valid traceparent from the output header, with the same trace_id but different parent_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01",],],
            )

        assert traceparent.trace_id == "12345678901234567890123456789012"
        assert traceparent.parent_id != "1234567890123456"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_included_tracestate_missing(self, test_agent, test_library):
        """
        harness sends a request with traceparent but without tracestate
        expects a valid traceparent from the output header, with the same trace_id but different parent_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01",],],
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
    def test_traceparent_duplicated(self, test_agent, test_library):
        """
        harness sends a request with two traceparent headers
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, _ = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789011-1234567890123456-01",],
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01",],
                ],
            )

        assert traceparent.trace_id != "12345678901234567890123456789011"
        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_header_name(self, test_agent, test_library):
        """
        harness sends an invalid traceparent using wrong names
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["trace-parent", "00-12345678901234567890123456789012-1234567890123456-01",],],
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["trace.parent", "00-12345678901234567890123456789012-1234567890123456-01",],],
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    @missing_feature(context.library == "ruby", reason="Ruby doesn't support case-insensitive distributed headers")
    def test_traceparent_header_name_valid_casing(self, test_agent, test_library):
        """
        harness sends a valid traceparent using different combination of casing
        expects a valid traceparent from the output header
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["TraceParent", "00-12345678901234567890123456789012-1234567890123456-01",],],
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["TrAcEpArEnT", "00-12345678901234567890123456789012-1234567890123456-01",],],
            )

            traceparent3, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["TRACEPARENT", "00-12345678901234567890123456789012-1234567890123456-01",],],
            )

        assert traceparent1.trace_id == "12345678901234567890123456789012"
        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert traceparent3.trace_id == "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_0x00(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with extra trailing characters
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01.",],],
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
        """
        harness sends an valid traceparent with future version 204 (0xcc)
        expects a valid traceparent from the output header with the same trace_id
        """
        with test_library:
            traceparent1, _ = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "cc-12345678901234567890123456789012-1234567890123456-01",],],
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
        """
        harness sends an invalid traceparent with version 255 (0xff)
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "ff-12345678901234567890123456789012-1234567890123456-01",],],
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_illegal_characters(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with illegal characters in version
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", ".0-12345678901234567890123456789012-1234567890123456-01",],],
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "0.-12345678901234567890123456789012-1234567890123456-01",],],
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_too_long(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with version more than 2 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "000-12345678901234567890123456789012-1234567890123456-01",],],
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "0000-12345678901234567890123456789012-1234567890123456-01",],],
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_version_too_short(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with version less than 2 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "0-12345678901234567890123456789012-1234567890123456-01",],],
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_id_all_zero(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with trace_id = 00000000000000000000000000000000
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-00000000000000000000000000000000-1234567890123456-01",],],
            )

        assert traceparent.trace_id != "00000000000000000000000000000000"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_id_illegal_characters(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with illegal characters in trace_id
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-.2345678901234567890123456789012-1234567890123456-01",],],
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-1234567890123456789012345678901.-1234567890123456-01",],],
            )

        assert traceparent1.trace_id != ".2345678901234567890123456789012"
        assert traceparent2.trace_id != "1234567890123456789012345678901."

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_id_too_long(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with trace_id more than 32 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-123456789012345678901234567890123-1234567890123456-01",],],
            )

        assert traceparent.trace_id != "123456789012345678901234567890123"
        assert traceparent.trace_id != "12345678901234567890123456789012"
        assert traceparent.trace_id != "23456789012345678901234567890123"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_id_too_short(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with trace_id less than 32 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-1234567890123456789012345678901-1234567890123456-01",],],
            )

        assert traceparent.trace_id != "1234567890123456789012345678901"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_parent_id_all_zero(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with parent_id = 0000000000000000
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-0000000000000000-01",],],
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_parent_id_illegal_characters(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with illegal characters in parent_id
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-.234567890123456-01",],],
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-123456789012345.-01",],],
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_parent_id_too_long(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with parent_id more than 16 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-12345678901234567-01",],],
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_parent_id_too_short(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with parent_id less than 16 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-123456789012345-01",],],
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_flags_illegal_characters(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with illegal characters in trace_flags
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-.0",],],
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-0.",],],
            )

        assert traceparent1.trace_id != "12345678901234567890123456789012"
        assert traceparent2.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_flags_too_long(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with trace_flags more than 2 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, _ = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-001",],],
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_trace_flags_too_short(self, test_agent, test_library):
        """
        harness sends an invalid traceparent with trace_flags less than 2 HEXDIG
        expects a valid traceparent from the output header, with a newly generated trace_id
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-1",],],
            )

        assert traceparent.trace_id != "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_traceparent_ows_handling(self, test_agent, test_library):
        """
        harness sends an valid traceparent with heading and trailing OWS
        expects a valid traceparent from the output header
        """
        with test_library:
            traceparent1, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", " 00-12345678901234567890123456789012-1234567890123456-01",],],
            )

            traceparent2, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "\t00-12345678901234567890123456789012-1234567890123456-01",],],
            )

            traceparent3, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01 ",],],
            )

            traceparent4, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "00-12345678901234567890123456789012-1234567890123456-01\t",],],
            )

            traceparent5, tracestate = make_single_request_and_get_tracecontext(
                test_library, [["traceparent", "\t 00-12345678901234567890123456789012-1234567890123456-01 \t",],],
            )

        assert traceparent1.trace_id == "12345678901234567890123456789012"
        assert traceparent2.trace_id == "12345678901234567890123456789012"
        assert traceparent3.trace_id == "12345678901234567890123456789012"
        assert traceparent4.trace_id == "12345678901234567890123456789012"
        assert traceparent5.trace_id == "12345678901234567890123456789012"

    @temporary_enable_optin_tracecontext()
    def test_tracestate_included_traceparent_missing(self, test_agent, test_library):
        """
        harness sends a request with tracestate but without traceparent
        expects a valid traceparent from the output header
        expects the tracestate to be discarded
        """
        with test_library:
            _, tracestate1 = make_single_request_and_get_tracecontext(test_library, [["tracestate", "foo=1"],])
            _, tracestate2 = make_single_request_and_get_tracecontext(test_library, [["tracestate", "foo=1,bar=2"],])

        # Updated the test to check that the number of tracestate list-members is the same,
        # since Datadog will add an entry.
        assert len(tracestate1.split(",")) == len(tracestate2.split(","))

    @temporary_enable_optin_tracecontext()
    def test_tracestate_included_traceparent_included(self, test_agent, test_library):
        """
        harness sends a request with both tracestate and traceparent
        expects a valid traceparent from the output header with the same trace_id
        expects the tracestate to be inherited
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1,bar=2"],
                ],
            )

        assert traceparent.trace_id == "12345678901234567890123456789012"
        assert tracestate["foo"] == "1"
        assert tracestate["bar"] == "2"

    @temporary_enable_optin_tracecontext()
    def test_tracestate_header_name(self, test_agent, test_library):
        """
        harness sends an invalid tracestate using wrong names
        expects the tracestate to be discarded
        """
        with test_library:
            traceparent, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["trace-state", "foo=1"],
                ],
            )

            traceparent, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["trace.state", "foo=1"],
                ],
            )

        assert "foo" not in tracestate1
        assert "foo" not in tracestate2

    @temporary_enable_optin_tracecontext()
    @missing_feature(context.library == "ruby", reason="Ruby doesn't support case-insensitive distributed headers")
    def test_tracestate_header_name_valid_casing(self, test_agent, test_library):
        """
        harness sends a valid tracestate using different combination of casing
        expects the tracestate to be inherited
        """
        with test_library:
            traceparent, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",], ["TraceState", "foo=1"],],
            )

            traceparent, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",], ["TrAcEsTaTe", "foo=1"],],
            )

            traceparent, tracestate3 = make_single_request_and_get_tracecontext(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",], ["TRACESTATE", "foo=1"],],
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
    def test_tracestate_empty_header(self, test_agent, test_library):
        """
        harness sends a request with empty tracestate header
        expects the empty tracestate to be discarded
        """
        with test_library:
            traceparent1, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",], ["tracestate", ""],],
            )

            traceparent2, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1"],
                    ["tracestate", ""],
                ],
            )

            traceparent3, tracestate3 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
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
    def test_tracestate_multiple_headers_different_keys(self, test_agent, test_library):
        """
        harness sends a request with multiple tracestate headers, each contains different set of keys
        expects a combined tracestate
        """
        with test_library:
            traceparent, tracestate = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
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
        """
        harness sends a request with an invalid tracestate header with duplicated keys
        expects the tracestate to be inherited, and the duplicated keys to be either kept as-is or one of them
        to be discarded
        """
        with test_library:
            traceparent1, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1,foo=1"],
                ],
            )

            traceparent2, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1,foo=2"],
                ],
            )

            traceparent3, tracestate3 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1"],
                    ["tracestate", "foo=1"],
                ],
            )

            traceparent4, tracestate4 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
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
    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library < "php@0.99.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.6.0", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.0.0", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    def test_tracestate_w3c_p_extract(self, test_agent, test_library):
        """
        Ensure the last parent id tag is set according to the W3C spec
        """
        with test_library:
            with test_library.start_span(
                name="p_set",
                http_headers=[
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-01"],
                    ["tracestate", "key1=value1,dd=s:2;o:rum;p:0123456789abcdef;t.dm:-4;t.usr.id:12345~"],
                ],
            ):
                pass

            with test_library.start_span(
                name="p_invalid",
                http_headers=[
                    ["traceparent", "00-12345678901234567890123456789013-1234567890123457-01"],
                    ["tracestate", "key1=value1,dd=s:2;t.dm:-4;p:XX!X"],
                ],
            ):
                pass

            with test_library.start_span(
                name="datadog_headers_used_in_propagation",
                http_headers=[
                    ["traceparent", "00-12345678901234567890123456789014-1234567890123458-00"],
                    ["tracestate", "key1=value1,dd=s:2;p:000000000000000b"],
                    ["x-datadog-trace-id", "5"],
                    ["x-datadog-parent-id", "11"],
                ],
            ):
                pass

            with test_library.start_span(
                name="p_not_propagated",
                http_headers=[
                    ["traceparent", "00-12345678901234567890123456789015-1234567890123459-00"],
                    ["tracestate", "key1=value1,dd=s:2;t.dm:-4"],
                ],
            ):
                pass

        traces = test_agent.wait_for_num_traces(4)

        assert len(traces) == 4
        case1, case2, case3, case4 = traces[0][0], traces[1][0], traces[2][0], traces[3][0]

        assert case1["name"] == "p_set"
        assert case1["meta"]["_dd.parent_id"] == "0123456789abcdef"

        assert case2["name"] == "p_invalid"
        assert case2["meta"]["_dd.parent_id"] == "XX!X"

        assert case3["name"] == "datadog_headers_used_in_propagation"
        assert case3["trace_id"] == 5
        assert case3["parent_id"] == 11
        assert "_dd.parent_id" not in case3["meta"]

        assert case4["name"] == "p_not_propagated"
        assert case4["meta"]["_dd.parent_id"] == "0000000000000000"

    @missing_feature(context.library < "python@2.7.0", reason="Not implemented")
    @missing_feature(context.library == "dotnet", reason="Not implemented")
    @missing_feature(context.library < "php@0.99.0", reason="Not implemented")
    @missing_feature(context.library < "nodejs@5.6.0", reason="Not implemented")
    @missing_feature(context.library == "java", reason="Not implemented")
    @missing_feature(context.library == "cpp", reason="Not implemented")
    @missing_feature(context.library < "ruby@2.0.0", reason="Not implemented")
    @missing_feature(context.library == "golang", reason="Not implemented")
    def test_tracestate_w3c_p_inject(self, test_agent, test_library):
        """
        Ensure the last parent id is propagated according to the W3C spec
        """
        with test_library:
            with test_library.start_span(name="new_span") as span:
                pass

            headers = test_library.inject_headers(span.span_id)

            tracestate_headers = list(filter(lambda h: h[0].lower() == "tracestate", headers))
            assert len(tracestate_headers) == 1, headers

            tracestate = tracestate_headers[0][1]
            # FIXME: nodejs paramerric app sets span.span_id to a string, convert this to an int
            assert "p:{:016x}".format(int(span.span_id)) in tracestate

    @temporary_enable_optin_tracecontext()
    def test_tracestate_all_allowed_characters(self, test_agent, test_library):
        """
        harness sends a request with a valid tracestate header with all legal characters
        expects the tracestate to be inherited
        """
        key_without_vendor = "".join(
            ["".join(map(chr, range(0x61, 0x7A + 1))), "0123456789", "_", "-", "*", "/",]  # lcalpha  # DIGIT
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
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", key_without_vendor + "=" + value],
                ],
            )

            traceparent2, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
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
    def test_tracestate_ows_handling(self, test_agent, test_library):
        """
        harness sends a request with a valid tracestate header with OWS
        expects the tracestate to be inherited
        """
        with test_library:
            traceparent1, tracestate1 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1 \t , \t bar=2, \t baz=3"],
                ],
            )

            traceparent2, tracestate2 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1\t \t,\t \tbar=2,\t \tbaz=3"],
                ],
            )

            traceparent3, tracestate3 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", " foo=1"],
                ],
            )

            traceparent4, tracestate4 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "\tfoo=1"],
                ],
            )

            traceparent5, tracestate5 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1 "],
                ],
            )

            traceparent6, tracestate6 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
                    ["tracestate", "foo=1\t"],
                ],
            )

            traceparent7, tracestate7 = make_single_request_and_get_tracecontext(
                test_library,
                [
                    ["traceparent", "00-12345678901234567890123456789012-1234567890123456-00",],
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
    return get_tracecontext(make_single_request_and_get_inject_headers(test_library, headers_list))
