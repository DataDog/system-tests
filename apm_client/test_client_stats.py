import pytest

from .conftest import _TestTracer
from .conftest import go_library_server_factory
from .conftest import python_library_server_factory
from .conftest import dotnet_library_server_factory


parametrize = pytest.mark.parametrize
snapshot = pytest.mark.snapshot


@parametrize(
    "apm_test_server_factory",
    [
        python_library_server_factory,
        # go_library_server_factory,
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
def test_client_tracestats_top_level(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When two top level (service entry) spans are created
        Each has stats computed for it
    """
    with test_client.start_span(name="web.request", resource="/users", service="webserver") as span:
        with test_client.start_span(
            name="postgres.query", resource="SELECT 1", service="postgres", parent_id=span.span_id
        ):
            pass
    test_client.flush()

    requests = test_agent.v06_stats_requests()
    assert len(requests) == 1, "Only one stats request is expected"
    request = requests[0]["body"]
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
    assert postgres_stats["Type"] is None  # FIXME: add span type
    assert postgres_stats["Hits"] == 1
    assert postgres_stats["TopLevelHits"] == 1
    assert postgres_stats["Duration"] > 0

    web_stats = [s for s in stats if s["Name"] == "web.request"][0]
    assert web_stats["Resource"] == "/users"
    assert web_stats["Service"] == "webserver"
    assert web_stats["Type"] is None  # FIXME: add span type
    assert web_stats["Hits"] == 1
    assert web_stats["TopLevelHits"] == 1
    assert web_stats["Duration"] > 0


@snapshot(
    ignores=[
        "error",
        "type",
        "meta.language",
        "metrics.process_id",
        "metrics._dd.agent_psr",
        "metrics._dd.tracer_kr",
        "metrics._sampling_priority_v1",
    ],
    # Specify a custom token so all parametrizations use the same snapshots
    token="apm_client.test_client_stats.test_client_snapshot",
)
@parametrize(
    "apm_test_server_factory",
    [
        python_library_server_factory,
        # go_library_server_factory,
        dotnet_library_server_factory,
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
