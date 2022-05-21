import contextlib
import os

import attr
import ddtrace
from ddtrace.internal.compat import parse, to_unicode
from ddtrace.internal.compat import httplib
from ddtrace.internal.utils.formats import parse_tags_str
import pytest

from apm_client.protos import apm_test_client_pb2 as pb
from apm_client.protos import apm_test_client_pb2_grpc


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )


@attr.s
class SnapshotTest(object):
    token = attr.ib(type=str)
    tracer = attr.ib(type=ddtrace.Tracer, default=ddtrace.tracer)

    def clear(self):
        """Clear any traces sent that were sent for this snapshot."""
        parsed = parse.urlparse(self.tracer.agent_trace_url)
        conn = httplib.HTTPConnection(parsed.hostname, parsed.port)
        conn.request("GET", "/test/session/clear?test_session_token=%s" % self.token)
        resp = conn.getresponse()
        assert resp.status == 200


@contextlib.contextmanager
def _snapshot_context(token, ignores=None, tracer=None, async_mode=True, variants=None):
    # Use variant that applies to update test token. One must apply. If none
    # apply, the test should have been marked as skipped.
    if variants:
        applicable_variant_ids = [k for (k, v) in variants.items() if v]
        assert len(applicable_variant_ids) == 1
        variant_id = applicable_variant_ids[0]
        token = "{}_{}".format(token, variant_id) if variant_id else token

    ignores = ignores or []
    if not tracer:
        tracer = ddtrace.tracer

    parsed = parse.urlparse(tracer._writer.agent_url)
    conn = httplib.HTTPConnection(parsed.hostname, parsed.port)
    try:
        # clear queue in case traces have been generated before test case is
        # itself run
        try:
            tracer._writer.flush_queue()
        except Exception as e:
            pytest.fail("Could not flush the queue before test case: %s" % str(e), pytrace=True)

        if async_mode:
            # Patch the tracer writer to include the test token header for all requests.
            tracer._writer._headers["X-Datadog-Test-Session-Token"] = token

            # Also add a header to the environment for subprocesses test cases that might use snapshotting.
            existing_headers = parse_tags_str(os.environ.get("_DD_TRACE_WRITER_ADDITIONAL_HEADERS", ""))
            existing_headers.update({"X-Datadog-Test-Session-Token": token})
            os.environ["_DD_TRACE_WRITER_ADDITIONAL_HEADERS"] = ",".join(
                ["%s:%s" % (k, v) for k, v in existing_headers.items()]
            )

        try:
            conn.request("GET", "/test/session/start?test_session_token=%s" % token)
        except Exception as e:
            pytest.fail("Could not connect to test agent: %s" % str(e), pytrace=False)
        else:
            r = conn.getresponse()
            if r.status != 200:
                # The test agent returns nice error messages we can forward to the user.
                pytest.fail(to_unicode(r.read()), pytrace=False)

        try:
            yield SnapshotTest(
                tracer=tracer,
                token=token,
            )
        finally:
            # Force a flush so all traces are submitted.
            tracer._writer.flush_queue()
            if async_mode:
                del tracer._writer._headers["X-Datadog-Test-Session-Token"]
                del os.environ["_DD_TRACE_WRITER_ADDITIONAL_HEADERS"]

        # Query for the results of the test.
        conn = httplib.HTTPConnection(parsed.hostname, parsed.port)
        conn.request("GET", "/test/session/snapshot?ignores=%s&test_session_token=%s" % (",".join(ignores), token))
        r = conn.getresponse()
        if r.status != 200:
            pytest.fail(to_unicode(r.read()), pytrace=False)
    except Exception as e:
        # Even though it's unlikely any traces have been sent, make the
        # final request to the test agent so that the test case is finished.
        conn = httplib.HTTPConnection(parsed.hostname, parsed.port)
        conn.request("GET", "/test/session/snapshot?ignores=%s&test_session_token=%s" % (",".join(ignores), token))
        conn.getresponse()
        pytest.fail("Unexpected test failure during snapshot test: %s" % str(e), pytrace=True)
    finally:
        conn.close()

def _request_token(request):
    token = ""
    token += request.module.__name__
    token += ".%s" % request.cls.__name__ if request.cls else ""
    token += ".%s" % request.node.name
    return token


@pytest.fixture(autouse=True)
def snapshot(request):
    marks = [m for m in request.node.iter_markers(name="snapshot")]
    assert len(marks) < 2, "Multiple snapshot marks detected"
    if marks:
        snap = marks[0]
        token = snap.kwargs.get("token")
        if token:
            del snap.kwargs["token"]
        else:
            token = _request_token(request).replace(" ", "_").replace(os.path.sep, "_")

        with _snapshot_context(token, *snap.args, **snap.kwargs) as snapshot:
            yield snapshot
    else:
        yield


@pytest.fixture
def snapshot_context(request):
    """
    Fixture to provide a context manager for executing code within a ``tests.utils.snapshot_context``
    with a default ``token`` based on the test function/``pytest`` request.

    def test_case(snapshot_context):
        with snapshot_context():
            # my code
    """
    token = _request_token(request)

    @contextlib.contextmanager
    def _snapshot(**kwargs):
        if "token" not in kwargs:
            kwargs["token"] = token
        with _snapshot_context(**kwargs) as snapshot:
            yield snapshot

    return _snapshot
