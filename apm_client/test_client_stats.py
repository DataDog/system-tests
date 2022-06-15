import pytest

from .conftest import _TestTracer
from .conftest import go_library_server_factory
from .conftest import python_library_server_factory


parametrize = pytest.mark.parametrize
snapshot = pytest.mark.snapshot


@snapshot(ignores=["error"])
@parametrize(
    "apm_test_server_factory",
    [
        python_library_server_factory,
        go_library_server_factory,
    ],
)
@parametrize(
    "apm_test_server_env",
    [
        {
            "DD_TRACE_COMPUTE_STATS": "1",
        },
    ],
)
def test_client_tracestats(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    print(apm_test_server_factory)
    with test_client.start_span(name="web.request", resource="/users", service="webserver") as span:
        with test_client.start_span(
            name="postgres.query", resource="SELECT 1", service="postgres", parent_id=span.span_id
        ):
            pass
    test_client.flush()

    requests = test_agent.requests()
    traces = test_agent.traces()
    stats = test_agent.tracestats()
    print(stats)

    assert len(stats) == 1, "Only one stats payload is expected"

    request = stats[0]
    for key in ("Hostname", "Env", "Version", "Stats"):
        assert key in request, "%r should be in stats request" % key

    buckets = request["Stats"]
    assert len(buckets) == 1, "There should be one bucket containing the stats"
    bucket = buckets[0]
    assert "Start" in bucket
    assert "Duration" in bucket
    assert "Stats" in bucket
    stats = bucket["Stats"]
    assert len(stats) == 2, "There should be two stats entries in the bucket"

    postgres_stats = [s for s in stats if s["Name"] == "postgres.query"][0]
    assert postgres_stats["Resource"] == "SELECT 1"
    assert postgres_stats["Service"] == "postgres"


@snapshot(
    ignores=["error"],
    # Specify a custom token so all parametrizations use the same snapshots
    token="apm_client.test_client_stats.test_client_snapshot",
)
@parametrize(
    "apm_test_server_factory",
    [
        python_library_server_factory,
        go_library_server_factory,
    ],
)
def test_client_snapshot(apm_test_server_factory, test_agent, test_client: _TestTracer):
    """Ensure clients mostly submit the same data for a trace.

    Data which is inconsistent enough between clients is ignored
    with the snapshot `ignores` argument.
    """
    with test_client.start_span(name="web.request", resource="/users", service="webserver") as span:
        span.set_meta("key", "val")
        with test_client.start_span(
            name="postgres.query", resource="SELECT 1", service="postgres", parent_id=span.span_id
        ):
            pass
