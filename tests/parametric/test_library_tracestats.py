import base64

import numpy as np
import msgpack
import pytest


from utils.docker_fixtures.spec.trace import SPAN_MEASURED_KEY
from utils.docker_fixtures.spec.trace import V06StatsAggr
from utils.docker_fixtures.spec.trace import find_root_span
from utils import context, scenarios, features, logger
from utils.docker_fixtures import TestAgentAPI
from .conftest import APMLibrary

parametrize = pytest.mark.parametrize


def _human_stats(stats: V06StatsAggr) -> str:
    """Return human-readable stats for debugging stat aggregations."""
    # Create a copy excluding 'ErrorSummary' and 'OkSummary' since TypedDicts don't allow delete
    filtered_copy = {k: v for k, v in stats.items() if k not in {"ErrorSummary", "OkSummary"}}
    return str(filtered_copy)


def _find_raw_v06_stats(test_agent: TestAgentAPI) -> dict:
    """Return the deserialized raw /v0.6/stats payload from the test agent.

    The decoded view exposed by `test_agent.get_v06_stats_requests()` is intentionally narrow
    (it omits fields like HTTPMethod, HTTPEndpoint, RuntimeID, Sequence). For spec assertions
    on those fields we need the raw msgpack body.
    """
    raw_body: str | None = None
    for request in test_agent.requests():
        if "v0.6/stats" in request["url"]:
            raw_body = request["body"]
    assert raw_body is not None, "Could not find /v0.6/stats request in test agent transcript"
    return msgpack.unpackb(base64.b64decode(raw_body))


def enable_tracestats(sample_rate: float | None = None) -> pytest.MarkDecorator:
    env = {
        "DD_TRACE_STATS_COMPUTATION_ENABLED": "1",  # reference, dotnet, python, golang
        "DD_TRACE_TRACER_METRICS_ENABLED": "true",  # java
    }
    if context.library == "golang" and context.library.version < "v1.55.0":
        env["DD_TRACE_FEATURES"] = "discovery"
    if sample_rate is not None:
        assert 0 <= sample_rate <= 1.0
        env.update({"DD_TRACE_SAMPLE_RATE": str(sample_rate)})

    return parametrize("library_env", [env])


def enable_agent_version(version: str = "7.65.0") -> pytest.MarkDecorator:
    """Set the test agent version. Java tracer requires agent version >= 7.65.0 for client-side stats."""
    agent_env_config = {"TEST_AGENT_VERSION": version}
    return parametrize("agent_env", [agent_env_config])


@scenarios.parametric
@features.client_side_stats_supported
class Test_Library_Tracestats:
    @enable_tracestats()
    @enable_agent_version()
    def test_metrics_msgpack_serialization_TS001(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When spans are finished
        Each trace has stats metrics computed for it serialized properly in msgpack format with required fields
        The required metrics are:
            {error_count, hit_count, ok/error latency distributions, duration}
        """
        with test_library, test_library.dd_start_span(name="web.request", resource="/users", service="webserver"):
            pass

        raw_requests = test_agent.requests()
        decoded_stats_requests = test_agent.get_v06_stats_requests()

        # find stats request (trace and stats requests are sent in different order between clients)
        raw_stats = None
        for request in raw_requests:
            if "v0.6/stats" in request["url"]:
                raw_stats = request["body"]
        assert raw_stats is not None, "Couldn't find raw stats request sent to test agent"
        deserialized_stats = msgpack.unpackb(base64.b64decode(raw_stats))["Stats"][0]["Stats"][0]
        agent_decoded_stats = decoded_stats_requests[0]["body"]["Stats"][0]["Stats"][0]
        assert len(decoded_stats_requests) == 1
        assert len(decoded_stats_requests[0]["body"]["Stats"]) == 1
        logger.debug([_human_stats(s) for s in decoded_stats_requests[0]["body"]["Stats"][0]["Stats"]])
        assert deserialized_stats["Name"] == "web.request"
        assert deserialized_stats["Resource"] == "/users"
        assert deserialized_stats["Service"] == "webserver"
        for key in (
            "Name",
            "Resource",
            "Service",
            "Synthetics",
            "Hits",
            "TopLevelHits",
            "Duration",
            "Errors",
        ):
            assert deserialized_stats[key] == agent_decoded_stats[key]
        # OkSummary & ErrorSummary latency distributions require further proto decoding.
        # We can just verify that they are recorded and present in the stats bucket.
        assert deserialized_stats.get("OkSummary") is not None
        assert deserialized_stats.get("ErrorSummary") is not None
        assert agent_decoded_stats.get("OkSummary", None) is not None
        assert agent_decoded_stats.get("ErrorSummary", None) is not None

        decoded_request_body = decoded_stats_requests[0]["body"]
        for key in ("Hostname", "Env", "Version", "Stats"):
            assert key in decoded_request_body, f"{key} should be in stats request"

    @enable_tracestats()
    @enable_agent_version()
    def test_distinct_aggregationkeys_TS003(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When spans are created with a unique set of dimensions
        Each span has stats computed for it and is in its own bucket
        The dimensions are: { service, type, name, resource, HTTP_status_code, synthetics }
        """
        name = "name"
        resource = "resource"
        service = "service"
        span_type = "http"
        http_status_code = "200"
        origin = "rum"

        with test_library:
            # Baseline
            with test_library.dd_start_span(name=name, resource=resource, service=service, typestr=span_type) as span:
                span.set_meta(key="_dd.origin", val=origin)
                span.set_meta(key="http.status_code", val=http_status_code)

            # Unique Name
            with test_library.dd_start_span(
                name="unique-name", resource=resource, service=service, typestr=span_type
            ) as span:
                span.set_meta(key="_dd.origin", val=origin)
                span.set_meta(key="http.status_code", val=http_status_code)

            # Unique Resource
            with test_library.dd_start_span(
                name=name, resource="unique-resource", service=service, typestr=span_type
            ) as span:
                span.set_meta(key="_dd.origin", val=origin)
                span.set_meta(key="http.status_code", val=http_status_code)

            # Unique Service
            with test_library.dd_start_span(
                name=name, resource=resource, service="unique-service", typestr=span_type
            ) as span:
                span.set_meta(key="_dd.origin", val=origin)
                span.set_meta(key="http.status_code", val=http_status_code)

            # Unique Type
            with test_library.dd_start_span(
                name=name, resource=resource, service=service, typestr="unique-type"
            ) as span:
                span.set_meta(key="_dd.origin", val=origin)
                span.set_meta(key="http.status_code", val=http_status_code)

            # Unique Synthetics
            with test_library.dd_start_span(name=name, resource=resource, service=service, typestr=span_type) as span:
                span.set_meta(key="_dd.origin", val="synthetics")
                span.set_meta(key="http.status_code", val=http_status_code)

            # Unique HTTP Status Code
            with test_library.dd_start_span(name=name, resource=resource, service=service, typestr=span_type) as span:
                span.set_meta(key="_dd.origin", val=origin)
                span.set_meta(key="http.status_code", val="400")

        if test_library.lang in ("golang", "java"):
            test_library.dd_flush()

        requests = test_agent.get_v06_stats_requests()
        assert len(requests) >= 1, "At least one stats request"
        cnt = 0
        for req in requests:
            request = req["body"]
            buckets = request["Stats"]
            assert len(buckets) == 1, "There should be one bucket containing the stats"

            bucket = buckets[0]
            stats = bucket["Stats"]
            cnt += len(stats)

            for s in stats:
                assert s["Hits"] == 1
                assert s["TopLevelHits"] == 1
                assert s["Duration"] > 0

        assert cnt == 7, (
            "There should be seven stats entries in the bucket. There is one baseline entry and 6 that are unique along each of 6 dimensions."
        )

    @enable_tracestats()
    @enable_agent_version()
    def test_measured_spans_TS004(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When spans are marked as measured
        Each has stats computed for it
        """
        with (
            test_library,
            test_library.dd_start_span(name="web.request", resource="/users", service="webserver") as span,
        ):
            # Use the same service so these spans are not top-level
            with test_library.dd_start_span(
                name="child.op1", resource="", service="webserver", parent_id=span.span_id
            ) as op1:
                op1.set_metric(SPAN_MEASURED_KEY, 1)
            with test_library.dd_start_span(
                name="child.op2", resource="", service="webserver", parent_id=span.span_id
            ) as op2:
                op2.set_metric(SPAN_MEASURED_KEY, 1)
            # Don't measure this one to ensure no stats are computed
            with test_library.dd_start_span(name="child.op3", resource="", service="webserver", parent_id=span.span_id):
                pass

        requests = test_agent.get_v06_stats_requests()
        assert len(requests) > 0
        assert len(requests[0]["body"]["Stats"]) != 0, "Stats should be computed"
        stats = requests[0]["body"]["Stats"][0]["Stats"]
        logger.debug([_human_stats(s) for s in stats])
        assert len(stats) == 3

        web_stats = [s for s in stats if s["Name"] == "web.request"][0]
        assert web_stats["TopLevelHits"] == 1
        op1_stats = [s for s in stats if s["Name"] == "child.op1"][0]
        assert op1_stats["Hits"] == 1
        assert op1_stats["TopLevelHits"] == 0
        op2_stats = [s for s in stats if s["Name"] == "child.op2"][0]
        assert op2_stats["Hits"] == 1
        assert op2_stats["TopLevelHits"] == 0

    @enable_tracestats()
    @enable_agent_version()
    def test_top_level_TS005(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When top level (service entry) spans are created
        Each top level span has trace stats computed for it.
        """
        with (
            test_library,
            # Create a top level span.
            test_library.dd_start_span(name="web.request", resource="/users", service="webserver") as span,
            # Create another top level (service entry) span as a child of the web.request span.
            test_library.dd_start_span(
                name="postgres.query", resource="SELECT 1", service="postgres", parent_id=span.span_id
            ),
        ):
            pass

        requests = test_agent.get_v06_stats_requests()
        assert len(requests) == 1, "Only one stats request is expected"
        request = requests[0]["body"]
        for key in ("Hostname", "Env", "Version", "Stats"):
            assert key in request, f"{key} should be in stats request"

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

    @enable_tracestats()
    @enable_agent_version()
    def test_successes_errors_recorded_separately_TS006(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When spans are marked as errors
        The errors count is incremented appropriately and the stats are aggregated into the ErrorSummary
        """
        with test_library:
            # Send 2 successes
            with test_library.dd_start_span(
                name="web.request", resource="/health-check", service="webserver", typestr="web"
            ):
                pass

            with test_library.dd_start_span(
                name="web.request", resource="/health-check", service="webserver", typestr="web"
            ):
                pass

            # Send 1 failure
            with test_library.dd_start_span(
                name="web.request", resource="/health-check", service="webserver", typestr="web"
            ) as span:
                span.set_error(message="Unable to load resources")

        requests = test_agent.get_v06_stats_requests()
        assert len(requests) == 1, "Only one stats request is expected"
        request = requests[0]["body"]
        for key in ("Hostname", "Env", "Version", "Stats"):
            assert key in request, f"{key} should be in stats request"

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

    @enable_tracestats(sample_rate=0.0)
    @enable_agent_version()
    def test_sample_rate_0_TS007(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When the sample rate is 0 and trace stats is enabled
        non-P0 traces should be dropped
        trace stats should be produced
        """
        with test_library, test_library.dd_start_span(name="web.request", resource="/users", service="webserver"):
            pass

        traces = test_agent.traces()
        assert len(traces) == 0, "No traces should be emitted with the sample rate set to 0"

        requests = test_agent.get_v06_stats_requests()
        assert len(requests) != 0, "Stats request should be sent"
        assert len(requests[0]["body"]["Stats"]) != 0, "Stats should be computed"
        stats = requests[0]["body"]["Stats"][0]["Stats"]
        assert len(stats) == 1, "Only one stats aggregation is expected"
        web_stats = [s for s in stats if s["Name"] == "web.request"][0]
        assert web_stats["TopLevelHits"] == 1
        assert web_stats["Hits"] == 1

    @enable_tracestats()
    @enable_agent_version()
    def test_relative_error_TS008(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When trace stats are computed for traces
            The stats should be accurate to within 1% of the real values

        Note that this test uses the duration of actual spans created and so this test could be flaky.
        This flakyness however would indicate a bug in the trace stats computation.
        """

        with test_library:
            # Create 10 traces to get more data
            for _ in range(10):
                with test_library.dd_start_span(name="web.request", resource="/users", service="webserver"):
                    pass

        traces = test_agent.traces()
        assert len(traces) == 10

        durations: list[int] = []
        for trace in traces:
            span = find_root_span(trace)
            assert span is not None
            durations.append(span["duration"])

        requests = test_agent.get_v06_stats_requests()

        assert len(requests) != 0, "Stats request should be sent"
        assert len(requests[0]["body"]["Stats"]) != 0, "Stats should be computed"
        stats = requests[0]["body"]["Stats"][0]["Stats"]
        assert len(stats) == 1, "Only one stats aggregation is expected"

        web_stats = [s for s in stats if s["Name"] == "web.request"][0]
        assert web_stats["TopLevelHits"] == 10
        assert web_stats["Hits"] == 10

        # Validate the sketches
        np_duration = np.array(durations)
        assert web_stats["Duration"] == sum(durations), "Stats duration should match the span duration exactly"
        for quantile in (0.5, 0.75, 0.95, 0.99, 1):
            assert web_stats["OkSummary"].get_quantile_value(quantile) == pytest.approx(
                np.quantile(np_duration, quantile),
                rel=0.01,
            ), f"Quantile mismatch for quantile {quantile!r}"

    @enable_tracestats()
    @enable_agent_version()
    def test_metrics_computed_after_span_finsh_TS009(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When trace stats are computed for traces
        Metrics must be computed after spans are finished, otherwise components of the aggregation key may change after
        contribution to aggregates.
        """
        name = "name"
        resource = "resource"
        service = "service"
        span_type = "http"
        http_status_code = "200"
        origin = "synthetics"

        with test_library:
            with test_library.dd_start_span(name=name, service=service, resource=resource, typestr=span_type) as span:
                span.set_meta(key="_dd.origin", val=origin)
                span.set_meta(key="http.status_code", val=http_status_code)

            with test_library.dd_start_span(name=name, service=service, resource=resource, typestr=span_type) as span2:
                span2.set_meta(key="_dd.origin", val=origin)
                span2.set_meta(key="http.status_code", val=http_status_code)

            # Span metrics should be calculated on span finish. Updating aggregation keys (service/resource/status_code/origin/etc.)
            # after span.finish() is called should not update stat buckets.
            span.set_meta(key="_dd.origin", val="not_synthetics")
            span.set_meta(key="http.status_code", val="202")
            span2.set_meta(key="_dd.origin", val="not_synthetics")
            span2.set_meta(key="http.status_code", val="202")

        requests = test_agent.get_v06_stats_requests()

        assert len(requests) == 1, "Only one stats request is expected"
        request = requests[0]["body"]
        buckets = request["Stats"]
        assert len(buckets) == 1, "There should be one bucket containing the stats"

        bucket = buckets[0]
        stats = bucket["Stats"]
        assert len(stats) == 1, (
            "There should be one stats entry in the bucket which contains stats for 2 top level spans"
        )

        assert stats[0]["Name"] == name
        assert stats[0]["TopLevelHits"] == 2
        assert stats[0]["Duration"] > 0
        # Ensure synthetics and http status code were not updated after span was finished
        assert stats[0]["HTTPStatusCode"] == int(http_status_code)
        assert stats[0]["Synthetics"] is True

    @parametrize("library_env", [{"DD_TRACE_STATS_COMPUTATION_ENABLED": "0"}])
    def test_metrics_computed_after_span_finish_TS010(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When DD_TRACE_STATS_COMPUTATION_ENABLED=False
        Metrics must be computed after spans are finished, otherwise components of the aggregation key may change after
        contribution to aggregates.
        """
        with test_library, test_library.dd_start_span(name="name", service="service", resource="resource") as span:
            span.set_meta(key="_dd.origin", val="synthetics")
            span.set_meta(key="http.status_code", val="200")

        requests = test_agent.get_v06_stats_requests()
        assert len(requests) == 0, "No stats were computed"

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "1",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",
                # dd-trace-java only extracts HTTPMethod/HTTPEndpoint when this is on.
                "DD_TRACE_RESOURCE_RENAMING_ENABLED": "true",
            }
        ],
    )
    @enable_agent_version()
    def test_http_method_endpoint_TS011(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """When spans carry HTTP method and endpoint metadata
        The stats aggregation entry must include HTTPMethod and HTTPEndpoint fields populated from
        the span's http.method and http.endpoint/http.route metadata. CSS spec v1.2.0 §5 (ClientGroupedStats).
        """
        with (
            test_library,
            test_library.dd_start_span(name="web.request", resource="GET /users/:id", service="webserver") as span,
        ):
            span.set_meta(key="span.kind", val="server")
            span.set_meta(key="http.method", val="GET")
            # Tracers diverge on which tag they read for HTTP_endpoint: dd-trace-go uses `http.endpoint`,
            # others may use `http.route`. Set both so this test is implementation-agnostic.
            span.set_meta(key="http.endpoint", val="/users/:id")
            span.set_meta(key="http.route", val="/users/:id")
            span.set_meta(key="http.status_code", val="200")

        raw_stats = _find_raw_v06_stats(test_agent)
        stats_entries = raw_stats["Stats"][0]["Stats"]
        web_entry = next((s for s in stats_entries if s.get("Name") == "web.request"), None)
        assert web_entry is not None, f"web.request stats entry not found in {stats_entries}"

        assert web_entry.get("HTTPMethod") == "GET", (
            f"Expected HTTPMethod='GET' in stats, got: {web_entry.get('HTTPMethod')!r}"
        )
        assert web_entry.get("HTTPEndpoint") == "/users/:id", (
            f"Expected HTTPEndpoint='/users/:id' in stats, got: {web_entry.get('HTTPEndpoint')!r}"
        )

    @parametrize(
        "library_env",
        [
            {
                "DD_TRACE_STATS_COMPUTATION_ENABLED": "1",
                "DD_TRACE_TRACER_METRICS_ENABLED": "true",
                # dd-trace-go and dd-trace-java only populate Hostname when DD_TRACE_REPORT_HOSTNAME
                # is on (option.go:297 / Config.java:2005). Pin both the flag and the value.
                "DD_TRACE_REPORT_HOSTNAME": "true",
                "DD_HOSTNAME": "test-host",
                # Spec §3 calls out env/service/version as deployment-level identifiers. Java's
                # WellKnownTags does not apply the spec's "unknown-env" default when DD_ENV is unset,
                # so we pin all three explicitly for deterministic assertions across SDKs.
                "DD_ENV": "tracestats-env",
                "DD_SERVICE": "tracestats-service",
                "DD_VERSION": "1.2.3",
            }
        ],
    )
    @enable_agent_version()
    def test_payload_metadata_TS012(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """The ClientStatsPayload must include deployment-level metadata fields.
        CSS spec v1.2.0 §3 mandates Hostname, Env, Version, Service, RuntimeID, and Sequence are
        populated by the tracer (constant per tracer instance, deployment-level identifiers).
        """
        with test_library, test_library.dd_start_span(name="web.request", resource="/users", service="webserver"):
            pass

        raw_stats = _find_raw_v06_stats(test_agent)

        # Hostname / Env / Version / RuntimeID are deployment-wide and live at the payload level.
        for field in ("Hostname", "Env", "Version", "RuntimeID"):
            assert field in raw_stats, f"Required field {field!r} missing from payload: {list(raw_stats.keys())}"
            value = raw_stats[field]
            assert isinstance(value, str), f"{field} must be a string, got {type(value)}"
            assert value, f"{field} must be a non-empty string, got {value!r}"

        # Sequence may legitimately be 0 on the first payload, so only require it's an int.
        assert "Sequence" in raw_stats, f"Sequence missing from payload: {list(raw_stats.keys())}"
        assert isinstance(raw_stats["Sequence"], int), f"Sequence must be int, got {type(raw_stats['Sequence'])}"

        # Service is allowed at the payload level OR at the per-bucket ClientGroupedStats level.
        # dd-trace-go intentionally only writes it per-bucket (stats.go:181), and the trace-agent
        # accepts that — it just loses one partition-key dimension during inter-payload aggregation
        # (client_stats_aggregator.go:178). The bucket-level Service is the spec-required source of
        # truth that the backend ultimately consumes.
        payload_service = raw_stats.get("Service") or ""
        bucket_services = {
            s.get("Service", "") for bucket in raw_stats.get("Stats", []) for s in bucket.get("Stats", [])
        }
        assert payload_service or any(bucket_services), (
            f"Expected Service either at payload level ({payload_service!r}) or in any "
            f"ClientGroupedStats ({bucket_services!r})"
        )

    @enable_tracestats()
    @enable_agent_version()
    def test_agent_populated_fields_empty_TS013(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """The tracer must leave agent-populated fields empty in the ClientStatsPayload.
        CSS spec v1.2.0 §3: ContainerID, Tags, ImageTag, AgentAggregation, and ProcessTagsHash
        are populated by the agent and must be empty/absent when the payload leaves the tracer.
        """
        with test_library, test_library.dd_start_span(name="web.request", resource="/users", service="webserver"):
            pass

        raw_stats = _find_raw_v06_stats(test_agent)

        # Each of these may either be absent from the msgpack payload or present with an empty value.
        for field in ("ContainerID", "ImageTag", "AgentAggregation"):
            value = raw_stats.get(field)
            assert value in (None, "", b""), (
                f"{field} must be left empty by the tracer for the agent to populate, got: {value!r}"
            )

        tags = raw_stats.get("Tags")
        assert tags in (None, [], ()), f"Tags must be left empty for the agent to populate, got: {tags!r}"

        process_tags_hash = raw_stats.get("ProcessTagsHash")
        assert process_tags_hash in (None, 0), (
            f"ProcessTagsHash must be left empty/zero for the agent to populate, got: {process_tags_hash!r}"
        )

    @enable_tracestats()
    @enable_agent_version()
    def test_partial_version_excluded_TS014(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Spans marked as partial snapshots (`_dd.partial_version` >= 0) must NOT contribute to stats.
        CSS spec v1.2.0 §7 (Span Exclusions).
        """
        with test_library:
            # A normal top-level span — must produce stats.
            with test_library.dd_start_span(name="web.request", resource="/users", service="webserver", typestr="web"):
                pass

            # A span flagged as a partial snapshot — must NOT produce stats.
            with test_library.dd_start_span(
                name="partial.snapshot", resource="/partial", service="webserver", typestr="web"
            ) as partial_span:
                partial_span.set_metric(key="_dd.partial_version", val=0)

        raw_stats = _find_raw_v06_stats(test_agent)
        stats_entries = raw_stats["Stats"][0]["Stats"]
        names = {s.get("Name") for s in stats_entries}

        assert "web.request" in names, (
            f"Sanity check: regular span should produce stats, but web.request missing from {names}"
        )
        assert "partial.snapshot" not in names, (
            f"Spans with _dd.partial_version set must be excluded from stats, but found in {names}"
        )
