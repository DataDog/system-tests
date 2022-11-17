# Tests imported from https://github.com/w3c/trace-context/blob/84b583d86ecb7005a9eab8fed86ab7117b050b48/test/test.py
# which is licensed under the W3C 3-clause BSD License https://www.w3.org/Consortium/Legal/2008/03-bsd-license.html.
from typing import Any

import pytest

from parametric.protos.apm_test_client_pb2 import DistributedHTTPHeaders
from parametric.spec.tracecontext import get_tracecontext

parametrize = pytest.mark.parametrize

def temporary_enable_optin_tracecontext() -> Any:
    env = {
        "DD_TRACE_PROPAGATION_STYLE_EXTRACT": "tracecontext,W3C",  # dotnet
        "DD_TRACE_PROPAGATION_STYLE_INJECT": "tracecontext,W3C",  # dotnet
    }
    return parametrize("library_env", [env])

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_both_traceparent_and_tracestate_missing(test_agent, test_library):
    '''
    harness sends a request without traceparent or tracestate
    expects a valid traceparent from the output header
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [])

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_included_tracestate_missing(test_agent, test_library):
    '''
    harness sends a request with traceparent but without tracestate
    expects a valid traceparent from the output header, with the same trace_id but different parent_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-01'],
        ])

    assert traceparent.trace_id == '12345678901234567890123456789012'
    assert traceparent.parent_id != '1234567890123456'


@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Bug: The .NET Tracer accepts one of the traceparent headers instead of discarding the headers")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_duplicated(test_agent, test_library):
    '''
    harness sends a request with two traceparent headers
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789011-1234567890123456-01'],
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-01'],
        ])

    assert traceparent.trace_id != '12345678901234567890123456789011'
    assert traceparent.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_header_name(test_agent, test_library):
    '''
    harness sends an invalid traceparent using wrong names
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['trace-parent', '00-12345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['trace.parent', '00-12345678901234567890123456789012-1234567890123456-01'],
        ])

    assert traceparent1.trace_id != '12345678901234567890123456789012'
    assert traceparent2.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Bug: Header search is currently case-sensitive")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_header_name_valid_casing(test_agent, test_library):
    '''
    harness sends a valid traceparent using different combination of casing
    expects a valid traceparent from the output header
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['TraceParent', '00-12345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['TrAcEpArEnT', '00-12345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent3, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['TRACEPARENT', '00-12345678901234567890123456789012-1234567890123456-01'],
        ])

    assert traceparent1.trace_id == '12345678901234567890123456789012'
    assert traceparent2.trace_id == '12345678901234567890123456789012'
    assert traceparent3.trace_id == '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_version_0x00(test_agent, test_library):
    '''
    harness sends an invalid traceparent with extra trailing characters
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-01.'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-01-what-the-future-will-be-like'],
        ])

    assert traceparent1.trace_id != '12345678901234567890123456789012'
    assert traceparent2.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Bug: See https://www.w3.org/TR/trace-context/#versioning-of-traceparent for corrections . 1) We currently assert that version must be 00 2) We assert the length of the traceparent is exactly equal to 55")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_version_0xcc(test_agent, test_library):
    '''
    harness sends an valid traceparent with future version 204 (0xcc)
    expects a valid traceparent from the output header with the same trace_id
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', 'cc-12345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', 'cc-12345678901234567890123456789012-1234567890123456-01-what-the-future-will-be-like'],
        ])

        traceparent3, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', 'cc-12345678901234567890123456789012-1234567890123456-01.what-the-future-will-be-like'],
        ])

    assert traceparent1.trace_id == '12345678901234567890123456789012'
    assert traceparent2.trace_id == '12345678901234567890123456789012'
    assert traceparent3.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Bug: Version string ff should be considered invalid")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_version_0xff(test_agent, test_library):
    '''
    harness sends an invalid traceparent with version 255 (0xff)
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', 'ff-12345678901234567890123456789012-1234567890123456-01'],
        ])

    assert traceparent.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Bug: Version string has invalid characters and should be considered invalid")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_version_illegal_characters(test_agent, test_library):
    '''
    harness sends an invalid traceparent with illegal characters in version
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '.0-12345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '0.-12345678901234567890123456789012-1234567890123456-01'],
        ])

    assert traceparent1.trace_id != '12345678901234567890123456789012'
    assert traceparent2.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_version_too_long(test_agent, test_library):
    '''
    harness sends an invalid traceparent with version more than 2 HEXDIG
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '000-12345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '0000-12345678901234567890123456789012-1234567890123456-01'],
        ])

    assert traceparent1.trace_id != '12345678901234567890123456789012'
    assert traceparent2.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_version_too_short(test_agent, test_library):
    '''
    harness sends an invalid traceparent with version less than 2 HEXDIG
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '0-12345678901234567890123456789012-1234567890123456-01'],
        ])

    assert traceparent.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_trace_id_all_zero(test_agent, test_library):
    '''
    harness sends an invalid traceparent with trace_id = 00000000000000000000000000000000
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-00000000000000000000000000000000-1234567890123456-01'],
        ])

    assert traceparent.trace_id != '00000000000000000000000000000000'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Bug: trace-id string has invalid characters and should be considered invalid")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_trace_id_illegal_characters(test_agent, test_library):
    '''
    harness sends an invalid traceparent with illegal characters in trace_id
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-.2345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-1234567890123456789012345678901.-1234567890123456-01'],
        ])

    assert traceparent1.trace_id != '.2345678901234567890123456789012'
    assert traceparent2.trace_id != '1234567890123456789012345678901.'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_trace_id_too_long(test_agent, test_library):
    '''
    harness sends an invalid traceparent with trace_id more than 32 HEXDIG
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-123456789012345678901234567890123-1234567890123456-01'],
        ])

    assert traceparent.trace_id != '123456789012345678901234567890123'
    assert traceparent.trace_id != '12345678901234567890123456789012'
    assert traceparent.trace_id != '23456789012345678901234567890123'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_trace_id_too_short(test_agent, test_library):
    '''
    harness sends an invalid traceparent with trace_id less than 32 HEXDIG
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-1234567890123456789012345678901-1234567890123456-01'],
        ])

    assert traceparent.trace_id != '1234567890123456789012345678901'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Bug: Parent-id of all zeroes should be considered invalid")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_parent_id_all_zero(test_agent, test_library):
    '''
    harness sends an invalid traceparent with parent_id = 0000000000000000
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-0000000000000000-01'],
        ])

    assert traceparent.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Bug: trace-id string has invalid characters and should be considered invalid")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_parent_id_illegal_characters(test_agent, test_library):
    '''
    harness sends an invalid traceparent with illegal characters in parent_id
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-.234567890123456-01'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-123456789012345.-01'],
        ])

    assert traceparent1.trace_id != '12345678901234567890123456789012'
    assert traceparent2.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_parent_id_too_long(test_agent, test_library):
    '''
    harness sends an invalid traceparent with parent_id more than 16 HEXDIG
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-12345678901234567-01'],
        ])

    assert traceparent.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_parent_id_too_short(test_agent, test_library):
    '''
    harness sends an invalid traceparent with parent_id less than 16 HEXDIG
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-123456789012345-01'],
        ])

    assert traceparent.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_trace_flags_illegal_characters(test_agent, test_library):
    '''
    harness sends an invalid traceparent with illegal characters in trace_flags
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-.0'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-0.'],
        ])

    assert traceparent1.trace_id != '12345678901234567890123456789012'
    assert traceparent2.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_trace_flags_too_long(test_agent, test_library):
    '''
    harness sends an invalid traceparent with trace_flags more than 2 HEXDIG
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-001'],
        ])

    assert traceparent.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_trace_flags_too_short(test_agent, test_library):
    '''
    harness sends an invalid traceparent with trace_flags less than 2 HEXDIG
    expects a valid traceparent from the output header, with a newly generated trace_id
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-1'],
        ])

    assert traceparent.trace_id != '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_traceparent_ows_handling(test_agent, test_library):
    '''
    harness sends an valid traceparent with heading and trailing OWS
    expects a valid traceparent from the output header
    '''
    with test_library:
        traceparent1, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', ' 00-12345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent2, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '\t00-12345678901234567890123456789012-1234567890123456-01'],
        ])

        traceparent3, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-01 '],
        ])

        traceparent4, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-01\t'],
        ])

        traceparent5, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '\t 00-12345678901234567890123456789012-1234567890123456-01 \t'],
        ])

    assert traceparent1.trace_id == '12345678901234567890123456789012'
    assert traceparent2.trace_id == '12345678901234567890123456789012'
    assert traceparent3.trace_id == '12345678901234567890123456789012'
    assert traceparent4.trace_id == '12345678901234567890123456789012'
    assert traceparent5.trace_id == '12345678901234567890123456789012'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_included_traceparent_missing(test_agent, test_library):
    '''
    harness sends a request with tracestate but without traceparent
    expects a valid traceparent from the output header
    expects the tracestate to be discarded
    '''
    with test_library:
        traceparent, tracestate1 = make_single_request_and_get_tracecontext(test_library, [
            ['tracestate', 'foo=1'],
        ])
        traceparent, tracestate2 = make_single_request_and_get_tracecontext(test_library, [
            ['tracestate', 'foo=1,bar=2'],
        ])

    # Updated the test to check that the number of tracestate list-members is the same,
    # since Datadog will add an entry
    assert len(tracestate1.split(',')) == len(tracestate2.split(','))

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_included_traceparent_included(test_agent, test_library):
    '''
    harness sends a request with both tracestate and traceparent
    expects a valid traceparent from the output header with the same trace_id
    expects the tracestate to be inherited
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1,bar=2'],
        ])

    assert traceparent.trace_id.hex() == '12345678901234567890123456789012'
    assert tracestate['foo'] == '1'
    assert tracestate['bar'] == '2'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_header_name(test_agent, test_library):
    '''
    harness sends an invalid tracestate using wrong names
    expects the tracestate to be discarded
    '''
    with test_library:
        traceparent, tracestate1 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['trace-state', 'foo=1'],
        ])
        

        traceparent, tracestate2 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['trace.state', 'foo=1'],
        ])
    
    assert tracestate1['foo'] is None
    assert tracestate2['foo'] is None

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_header_name_valid_casing(test_agent, test_library):
    '''
    harness sends a valid tracestate using different combination of casing
    expects the tracestate to be inherited
    '''
    with test_library:
        traceparent, tracestate1 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['TraceState', 'foo=1'],
        ])

        traceparent, tracestate2 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['TrAcEsTaTe', 'foo=1'],
        ])

        traceparent, tracestate3 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['TRACESTATE', 'foo=1'],
        ])

    assert tracestate1['foo'] == '1'
    assert tracestate2['foo'] == '1'
    assert tracestate3['foo'] == '1'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_empty_header(test_agent, test_library):
    '''
    harness sends a request with empty tracestate header
    expects the empty tracestate to be discarded
    '''
    with test_library:
        traceparent1, tracestate1 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', ''],
        ])

        traceparent2, tracestate2 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1'],
            ['tracestate', ''],
        ])

        traceparent3, tracestate3 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', ''],
            ['tracestate', 'foo=1'],
        ])

    assert traceparent1.trace_id.hex() == '12345678901234567890123456789012'
    assert not tracestate1 or tracestate1 != ''

    assert traceparent2.trace_id.hex() == '12345678901234567890123456789012'
    assert tracestate2['foo'] == '1'

    assert traceparent3.trace_id.hex() == '12345678901234567890123456789012'
    assert tracestate3['foo'] == '1'

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_multiple_headers_different_keys(test_agent, test_library):
    '''
    harness sends a request with multiple tracestate headers, each contains different set of keys
    expects a combined tracestate
    '''
    with test_library:
        traceparent, tracestate = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1,bar=2'],
            ['tracestate', 'rojo=1,congo=2'],
            ['tracestate', 'baz=3'],
        ])
    
    assert traceparent.trace_id.hex() == '12345678901234567890123456789012'
    assert 'foo=1' in str(tracestate)
    assert 'bar=2' in str(tracestate)
    assert 'rojo=1' in str(tracestate)
    assert 'congo=2' in str(tracestate)
    assert 'baz=3' in str(tracestate)
    assert str(tracestate).index('foo=1') < str(tracestate).index('bar=2')
    assert str(tracestate).index('bar=2') < str(tracestate).index('rojo=1')
    assert str(tracestate).index('rojo=1') < str(tracestate).index('congo=2')
    assert str(tracestate).index('congo=2') < str(tracestate).index('baz=3')

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_duplicated_keys(test_agent, test_library):
    '''
    harness sends a request with an invalid tracestate header with duplicated keys
    expects the tracestate to be inherited, and the duplicated keys to be either kept as-is or one of them
    to be discarded
    '''
    with test_library:
        traceparent1, tracestate1 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1,foo=1'],
        ])

        traceparent2, tracestate2 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1,foo=2'],
        ])

        traceparent3, tracestate3 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1'],
            ['tracestate', 'foo=1'],
        ])

        traceparent4, tracestate4 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1'],
            ['tracestate', 'foo=2'],
        ])

    assert traceparent1.trace_id.hex() == '12345678901234567890123456789012'
    assert 'foo=1' in str(tracestate1)

    assert traceparent2.trace_id.hex() == '12345678901234567890123456789012'
    assert 'foo=1' in str(tracestate2) or 'foo=2' in str(tracestate2)

    assert traceparent3.trace_id.hex() == '12345678901234567890123456789012'
    assert 'foo=1' in str(tracestate3)

    assert traceparent4.trace_id.hex() == '12345678901234567890123456789012'
    assert 'foo=1' in str(tracestate4) or 'foo=2' in str(tracestate4)

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_all_allowed_characters(test_agent, test_library):
    '''
    harness sends a request with a valid tracestate header with all legal characters
    expects the tracestate to be inherited
    '''
    key_without_vendor = ''.join([
        ''.join(map(chr, range(0x61, 0x7A + 1))), # lcalpha
        '0123456789', # DIGIT
        '_',
        '-',
        '*',
        '/',
    ])
    key_with_vendor = key_without_vendor + '@a-z0-9_-*/'
    value = ''.join([
        ''.join(map(chr, range(0x20, 0x2B + 1))),
        ''.join(map(chr, range(0x2D, 0x3C + 1))),
        ''.join(map(chr, range(0x3E, 0x7E + 1))),
    ])

    with test_library:
        traceparent1, tracestate1 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', key_without_vendor + '=' + value],
        ])

        traceparent2, tracestate2 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', key_with_vendor + '=' + value],
        ])

    assert key_without_vendor in tracestate1
    assert tracestate1[key_without_vendor] == value

    assert key_with_vendor in tracestate2
    assert tracestate2[key_with_vendor] == value

@temporary_enable_optin_tracecontext()
@pytest.mark.skip_library("dotnet", "Tracestate not implemented")
@pytest.mark.skip_library("golang", "not implemented")
@pytest.mark.skip_library("nodejs", "not implemented")
@pytest.mark.skip_library("python", "not implemented")
def test_tracestate_ows_handling(test_agent, test_library):
    '''
    harness sends a request with a valid tracestate header with OWS
    expects the tracestate to be inherited
    '''
    with test_library:
        traceparent1, tracestate1 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1 \t , \t bar=2, \t baz=3'],
        ])

        traceparent2, tracestate2 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1\t \t,\t \tbar=2,\t \tbaz=3'],
        ])

        traceparent3, tracestate3 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', ' foo=1'],
        ])

        traceparent4, tracestate4 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', '\tfoo=1'],
        ])

        traceparent5, tracestate5 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1 '],
        ])

        traceparent6, tracestate6 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', 'foo=1\t'],
        ])

        traceparent7, tracestate7 = make_single_request_and_get_tracecontext(test_library, [
            ['traceparent', '00-12345678901234567890123456789012-1234567890123456-00'],
            ['tracestate', '\t foo=1 \t'],
        ])

    assert tracestate1['foo'] == '1'
    assert tracestate1['bar'] == '2'
    assert tracestate1['baz'] == '3'

    assert tracestate2['foo'] == '1'
    assert tracestate2['bar'] == '2'
    assert tracestate2['baz'] == '3'

    assert traceparent3.trace_id.hex() == '12345678901234567890123456789012'
    assert tracestate3['foo'] == '1'

    assert traceparent4.trace_id.hex() == '12345678901234567890123456789012'
    assert tracestate4['foo'] == '1'

    assert traceparent5.trace_id.hex() == '12345678901234567890123456789012'
    assert tracestate5['foo'] == '1'

    assert traceparent6.trace_id.hex() == '12345678901234567890123456789012'
    assert tracestate6['foo'] == '1'

    assert traceparent7.trace_id.hex() == '12345678901234567890123456789012'
    assert tracestate7['foo'] == '1'

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

def get_span(test_agent):
    traces = test_agent.traces()
    span = traces[0][0]
    return span

def make_single_request_and_get_tracecontext(test_library, headers_list):
    distributed_message = DistributedHTTPHeaders()
    for key, value in headers_list:
        distributed_message.http_headers[key] = value

    with test_library.start_span(
        name="name", service="service", resource="resource", http_headers=distributed_message
    ) as span:
        headers = test_library.inject_headers(span.span_id).http_headers.http_headers
        return get_tracecontext(headers)