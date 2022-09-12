import os
import pprint
from typing import Any
from typing import Optional
from typing import List
from typing import Tuple

import msgpack
import base64
import pytest
import numpy

from .conftest import dotnet_library_server_factory
from .conftest import golang_library_server_factory
from .conftest import python_library_server_factory
from .conftest import ClientLibraryServerFactory
from spec.trace import SPAN_MEASURED_KEY
from spec.trace import V06StatsAggr


parametrize = pytest.mark.parametrize
snapshot = pytest.mark.snapshot


def _human_stats(stats: V06StatsAggr) -> str:
    """Return human-readable stats for debugging stat aggregations."""
    copy = stats.copy()
    del copy["ErrorSummary"]
    del copy["OkSummary"]
    return str(copy)


def all_libs(skip=[]) -> Any:
    libs = {
        "python": python_library_server_factory,
        "dotnet": dotnet_library_server_factory,
        "golang": golang_library_server_factory,
    }
    enabled: List[Tuple[str, ClientLibraryServerFactory]] = []
    for lang in os.getenv("CLIENTS_ENABLED", "python,dotnet,golang").split(","):
        if lang in skip:
            continue
        enabled.append((lang, libs[lang]))
    print("client libraries enabled: %s" % ",".join([l for l, _ in enabled]))
    return parametrize("apm_test_server_factory", [factory for _, factory in enabled])


def enable_tracestats(sample_rate: Optional[float] = None) -> Any:
    env = {
        "DD_TRACE_STATS_COMPUTATION_ENABLED": "1",  # dotnet, reference
        "DD_TRACE_COMPUTE_STATS": "1",  # python
        "DD_TRACE_FEATURES": "discovery",  # golang
    }
    if sample_rate is not None:
        assert 0 <= sample_rate <= 1.0
        env.update(
            {"DD_TRACE_SAMPLE_RATE": str(sample_rate),}
        )
    return parametrize("apm_test_server_env", [env])


def disable_tracestats(sample_rate: Optional[float] = None) -> Any:
    return parametrize("apm_test_server_env", [{"DD_TRACE_STATS_COMPUTATION_ENABLED": "0"}])


@all_libs()
@enable_tracestats()
def test_metrics_msgpack_serialization_TS001(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When spans are finished
        Each trace has stats metrics computed for it serialized properly in msgpack format with required fields
        The required metrics are:
            {error_count, hit_count, ok/error latency distributions, sum of all durations (per unique aggregation key)}
    """
    with test_client.start_span(name="web.request", resource="/users", service="webserver"):
        pass
    test_client.flush()

    raw_requests = test_agent.requests()
    decoded_requests = test_agent.v06_stats_requests()
    assert len(raw_requests) == 2, "2 encoded requests are expected (Stats + Traces)"
    assert len(decoded_requests[0]["body"]["Stats"][0]["Stats"]) == 1, "Only one decoded stats request is expected"

    raw_stats = raw_requests[1]["body"]
    deserialized_stats = msgpack.unpackb(base64.b64decode(raw_stats))["Stats"][0]["Stats"][0]
    decoded_stats = decoded_requests[0]["body"]["Stats"][0]["Stats"][0]
    assert deserialized_stats["Name"] == "web.request"
    assert deserialized_stats["Resource"] == "/users"
    assert deserialized_stats["Service"] == "webserver"
    for key in (
        "Name",
        "Resource",
        "Service",
        "Type",
        "HTTPStatusCode",
        "Synthetics",
        "Hits",
        "TopLevelHits",
        "Duration",
        "Errors",
    ):
        assert deserialized_stats[key] == decoded_stats[key]
    # OkSummary & ErrorSummary require further proto decoding - check that it is recorded onto each stats bucket.
    assert decoded_stats.get("OkSummary", None) is not None
    assert decoded_stats.get("ErrorSummary", None) is not None

    decoded_request_body = decoded_requests[0]["body"]
    for key in ("Hostname", "Env", "Version", "Stats"):
        assert key in decoded_request_body, "%r should be in stats request" % key


@all_libs()
@enable_tracestats()
def test_distinct_aggregationkeys_TS003(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When spans are created with a unique set of dimensions
        Each span has stats computed for it and is in its own bucket
        The dimensions are: { service, type, name, resource, HTTP_status_code, synthetics }
    """
    name = "name"
    resource = "resource"
    service = "service"
    type = "http"
    http_status_code = "200"
    origin = "rum"

    # Baseline
    with test_client.start_span(name=name, resource=resource, service=service, typestr=type, origin=origin) as span:
        span.set_meta(key="http.status_code", val=http_status_code)

    # Unique Name
    with test_client.start_span(
        name="unique-name", resource=resource, service=service, typestr=type, origin=origin
    ) as span:
        span.set_meta(key="http.status_code", val=http_status_code)

    # Unique Resource
    with test_client.start_span(
        name=name, resource="unique-resource", service=service, typestr=type, origin=origin
    ) as span:
        span.set_meta(key="http.status_code", val=http_status_code)

    # Unique Service
    with test_client.start_span(
        name=name, resource=resource, service="unique-service", typestr=type, origin=origin
    ) as span:
        span.set_meta(key="http.status_code", val=http_status_code)

    # Unique Type
    with test_client.start_span(
        name=name, resource=resource, service=service, typestr="unique-type", origin=origin
    ) as span:
        span.set_meta(key="http.status_code", val=http_status_code)

    # Unique Synthetics
    with test_client.start_span(
        name=name, resource=resource, service=service, typestr=type, origin="synthetics"
    ) as span:
        span.set_meta(key="http.status_code", val=http_status_code)

    # Unique HTTP Status Code
    with test_client.start_span(name=name, resource=resource, service=service, typestr=type, origin=origin) as span:
        span.set_meta(key="http.status_code", val="400")

    test_client.flush()

    requests = test_agent.v06_stats_requests()
    assert len(requests) == 1, "Only one stats request is expected"
    request = requests[0]["body"]
    buckets = request["Stats"]
    assert len(buckets) == 1, "There should be one bucket containing the stats"

    bucket = buckets[0]
    stats = bucket["Stats"]
    assert (
        len(stats) == 7
    ), "There should be seven stats entries in the bucket. There is one baseline entry and 6 that are unique along each of 6 dimensions."

    for s in stats:
        assert s["Hits"] == 1
        assert s["TopLevelHits"] == 1
        assert s["Duration"] > 0


@all_libs()
@enable_tracestats()
@pytest.mark.skip_libraries(["dotnet"], "FIXME: test_agent.v06_stats_requests should return 3 stats NOT 4")
def test_measured_spans_TS004(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When spans are marked as measured
        Each has stats computed for it
    """
    with test_client.start_span(name="web.request", resource="/users", service="webserver") as span:
        # Use the same service so these spans are not top-level
        with test_client.start_span(name="child.op1", resource="", service="webserver", parent_id=span.span_id) as op1:
            op1.set_metric(SPAN_MEASURED_KEY, 1)
        with test_client.start_span(name="child.op2", resource="", service="webserver", parent_id=span.span_id) as op2:
            op2.set_metric(SPAN_MEASURED_KEY, 1)
        # Don't measure this one to ensure no stats are computed
        with test_client.start_span(name="child.op3", resource="", service="webserver", parent_id=span.span_id):
            pass
    test_client.flush()

    requests = test_agent.v06_stats_requests()
    stats = requests[0]["body"]["Stats"][0]["Stats"]
    pprint.pprint([_human_stats(s) for s in stats])
    # FIXME: dotnet AssertionError: assert 4 == 3
    assert len(stats) == 3

    web_stats = [s for s in stats if s["Name"] == "web.request"][0]
    assert web_stats["TopLevelHits"] == 1
    op1_stats = [s for s in stats if s["Name"] == "child.op1"][0]
    assert op1_stats["Hits"] == 1
    assert op1_stats["TopLevelHits"] == 0
    op2_stats = [s for s in stats if s["Name"] == "child.op2"][0]
    assert op2_stats["Hits"] == 1
    assert op2_stats["TopLevelHits"] == 0


@all_libs()
@enable_tracestats()
def test_top_level_TS005(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When top level (service entry) spans are created
        Each top level span has trace stats computed for it.
    """
    # Create a top level span.
    with test_client.start_span(name="web.request", resource="/users", service="webserver") as span:
        # Create another top level (service entry) span as a child of the web.request span.
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
    assert postgres_stats["Type"] in ["", None]  # FIXME: add span type
    assert postgres_stats["Hits"] == 1
    assert postgres_stats["TopLevelHits"] == 1
    assert postgres_stats["Duration"] > 0

    web_stats = [s for s in stats if s["Name"] == "web.request"][0]
    assert web_stats["Resource"] == "/users"
    assert web_stats["Service"] == "webserver"
    assert web_stats["Type"] in ["", None]
    assert web_stats["Hits"] == 1
    assert web_stats["TopLevelHits"] == 1
    assert web_stats["Duration"] > 0


@all_libs()
@enable_tracestats()
def test_successes_errors_recorded_separately_TS006(
    apm_test_server_env, apm_test_server_factory, test_agent, test_client
):
    """
    When spans are marked as errors
        The errors count is incremented appropriately and the stats are aggregated into the ErrorSummary
    """
    # Send 2 successes
    with test_client.start_span(name="web.request", resource="/health-check", service="webserver", typestr="web"):
        pass

    with test_client.start_span(name="web.request", resource="/health-check", service="webserver", typestr="web"):
        pass

    # Send 1 failure
    with test_client.start_span(
        name="web.request", resource="/health-check", service="webserver", typestr="web"
    ) as span:
        span.set_error(message="Unable to load resources")

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
    assert len(stats) == 1, "There should be one stats entry in the bucket"

    stat = stats[0]
    assert stat["Resource"] == "/health-check"
    assert stat["Service"] == "webserver"
    assert stat["Type"] == "web"
    assert stat["Hits"] == 3
    assert stat["Errors"] == 1
    assert stat["TopLevelHits"] == 3
    assert stat["Duration"] > 0
    assert stat["OkSummary"] is not None
    assert stat["ErrorSummary"] is not None


@all_libs()
@enable_tracestats(sample_rate=0.0)
@pytest.mark.skip_libraries(["dotnet"], "FIXME: No traces should be emitted with the sample rate set to 0")
def test_sample_rate_0_TS007(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When the sample rate is 0 and trace stats is enabled
        non-P0 traces should be dropped
        trace stats should be produced
    """
    with test_client.start_span(name="web.request", resource="/users", service="webserver"):
        pass
    test_client.flush()

    traces = test_agent.traces()
    # FIXME: dotnet AssertionError: len(traces) == 1
    assert len(traces) == 0, "No traces should be emitted with the sample rate set to 0"

    requests = test_agent.v06_stats_requests()
    stats = requests[0]["body"]["Stats"][0]["Stats"]
    assert len(stats) == 1, "Only one stats aggregation is expected"
    web_stats = [s for s in stats if s["Name"] == "web.request"][0]
    assert web_stats["TopLevelHits"] == 1
    assert web_stats["Hits"] == 1


@all_libs()
@enable_tracestats()
@pytest.mark.skip(reason="bronke")
def test_relative_error_TS008(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When trace stats are computed for traces
        The stats should be accurate to within 1% of the real values

    Note that this test uses the duration of actual spans created and so this test could be flaky.
    This flakyness however would indicate a bug in the trace stats computation.
    """

    # Create 10 traces to get more data
    for i in range(10):
        with test_client.start_span(name="web.request", resource="/users", service="webserver"):
            pass
    test_client.flush()

    traces = test_agent.traces()
    assert len(traces) == 10

    durations: List[int] = []
    for trace in traces:
        span = trace[0]["duration"]
        durations.append(span)

    requests = test_agent.v06_stats_requests()
    stats = requests[0]["body"]["Stats"][0]["Stats"]
    assert len(stats) == 1, "Only one stats aggregation is expected"
    web_stats = [s for s in stats if s["Name"] == "web.request"][0]
    assert web_stats["TopLevelHits"] == 10
    assert web_stats["Hits"] == 10

    # Validate the sketches
    np_duration = numpy.array(durations)
    assert web_stats["Duration"] == sum(durations), "Stats duration should match the span duration exactly"
    for quantile in (0.5, 0.75, 0.95, 0.99, 1):
        assert web_stats["OkSummary"].get_quantile_value(quantile) == pytest.approx(
            numpy.quantile(np_duration, quantile), rel=0.01,
        ), ("Quantile mismatch for quantile %r" % quantile)


@all_libs()
@enable_tracestats()
def test_metrics_computed_after_span_finsh_TS008(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When trace stats are computed for traces
        Metrics must be computed after spans are finished, otherwise components of the aggregation key may change after 
        contribution to aggregates.
    """
    name = "name"
    resource = "resource"
    service = "service"
    type = "http"
    http_status_code = "200"
    origin = "synthetics"

    with test_client.start_span(name=name, service=service, resource=resource, origin=origin) as span:
        span.set_meta(key="http.status_code", val=http_status_code)

    with test_client.start_span(name=name, service=service, resource=resource, origin=origin) as span2:
        span2.set_meta(key="http.status_code", val=http_status_code)

    # Span metrics should be calculated on span finish. Updating aggregation keys (service/resource/status_code/origin/etc.)
    # after span.finish() is called should not update stat buckets.
    span.set_meta(key="_dd.origin", val="not_synthetics")
    span.set_meta(key="http.status_code", val="202")
    span2.set_meta(key="_dd.origin", val="not_synthetics")
    span2.set_meta(key="http.status_code", val="202")

    test_client.flush()

    requests = test_agent.v06_stats_requests()

    assert len(requests) == 1, "Only one stats request is expected"
    request = requests[0]["body"]
    buckets = request["Stats"]
    assert len(buckets) == 1, "There should be one bucket containing the stats"

    bucket = buckets[0]
    stats = bucket["Stats"]
    assert len(stats) == 1, "There should be one stats entry in the bucket which contains stats for 2 top level spans"

    assert stats[0]["Name"] == name
    assert stats[0]["TopLevelHits"] == 2
    assert stats[0]["Duration"] > 0
    # Ensure synthetics and http status code were not updated after span was finished
    assert stats[0]["HTTPStatusCode"] == int(http_status_code)
    assert stats[0]["Synthetics"] is True


@disable_tracestats()
@all_libs()
def test_metrics_computed_after_span_finsh_TS010(apm_test_server_env, apm_test_server_factory, test_agent, test_client):
    """
    When DD_TRACE_STATS_COMPUTATION_ENABLED=False
        Metrics must be computed after spans are finished, otherwise components of the aggregation key may change after
        contribution to aggregates.
    """
    with test_client.start_span(name="name", service="service", resource="resource", origin="synthetics") as span:
        span.set_meta(key="http.status_code", val="200")

    test_client.flush()
    requests = test_agent.v06_stats_requests()
    assert len(requests) == 0, "No stats were computed"
