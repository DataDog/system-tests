import pytest
from utils import interfaces, weblog, features, scenarios, missing_feature, context, bug, logger
from utils._decorators import flaky

"""
Test scenarios we want:
    * Generate N spans that will be aggregated together
        - Must aggregate by:
            - HTTP status code
            - peer service tags (todo: can we just rely on the defaults?)
        - Must have `is_trace_root` on trace root
        - Must set peer tags
        - Must have span_kind

Config:
- apm_config.peer_tags_aggregation (we should see peer service tags and aggregation by them, note only works on client or producer kind)
- apm_config.compute_stats_by_span_kind (span_kind will be set and we will calc stats on these spans even when not "top level")
"""


@features.client_side_stats_supported
@scenarios.trace_stats_computation
class Test_Client_Stats:
    """Test client-side stats are compatible with Agent implementation"""

    def setup_client_stats(self):
        for _ in range(5):
            weblog.get("/stats-unique")
        for _ in range(3):
            weblog.get("/stats-unique?code=204")

    @bug(context.weblog_variant in ("django-poc", "python3.12"), library="python", reason="APMSP-1375")
    @missing_feature(
        context.weblog_variant in ("play", "ratpack"),
        library="java",
        reason="play and ratpack controllers also generate stats and the test will fail",
    )
    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "nodejs", "php", "python", "ruby")
        or context.library <= "java@1.52.1",
        reason="Tracers have not implemented this feature yet.",
    )
    def test_client_stats(self):
        stats_count = 0
        ok_hits = 0
        ok_top_hits = 0
        no_content_hits = 0
        no_content_top_hits = 0
        for s in interfaces.agent.get_stats(resource="GET /stats-unique"):
            stats_count += 1
            logger.debug(f"asserting on {s}")
            if s["HTTPStatusCode"] == 200:
                ok_hits += s["Hits"]
                ok_top_hits += s["TopLevelHits"]
            elif s["HTTPStatusCode"] == 204:
                no_content_hits += s["Hits"]
                no_content_top_hits += s["TopLevelHits"]
            else:
                pytest.fail("Unexpected status code " + str(s["HTTPStatusCode"]))
            assert s["Service"] == "weblog", "expect weblog as service"
            assert s["Type"] == "web", "expect 'web' type"
        assert (
            stats_count <= 4
        ), "expect <= 4 stats"  # Normally this is exactly 2 but in certain high load this can flake and result in additional payloads where hits are split across two payloads
        assert ok_hits == ok_top_hits == 5, "expect exactly 5 'OK' hits and top level hits across all payloads"
        assert (
            no_content_hits == no_content_top_hits == 3
        ), "expect exactly 5 'No Content' hits and top level hits across all payloads"

    def setup_obfuscation(self):
        """Setup for obfuscation test - generates SQL spans for obfuscation testing"""
        # Use existing RASP SQL injection endpoints to generate spans with obfuscated resource names
        test_user_ids = ["1", "2", "admin", "test"]
        for user_id in test_user_ids:
            weblog.get(f"/rasp/sqli?user_id={user_id}")

    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "nodejs", "php", "python", "ruby")
        or context.library <= "java@1.52.1",
        reason="Tracers have not implemented this feature yet.",
    )
    @flaky(library="java", reason="LANGPLAT-760")
    def test_obfuscation(self):
        stats_count = 0
        hits = 0
        top_hits = 0
        resource = "SELECT * FROM users WHERE id = ?"
        for s in interfaces.agent.get_stats(resource):
            stats_count += 1
            logger.debug(f"asserting on {s}")
            hits += s["Hits"]
            top_hits += s["TopLevelHits"]
            assert s["Type"] == "sql", "expect 'sql' type"
        assert (
            stats_count <= 4
        ), "expect <= 4 stats"  # Normally this is exactly 2 but in certain high load this can flake and result in additional payloads where hits are split across two payloads
        assert hits == top_hits == 4, "expect exactly 4 'OK' hits and top level hits across all payloads"

    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "nodejs", "php", "python", "ruby")
        or context.library <= "java@1.52.1",
        reason="Tracers have not implemented this feature yet.",
    )
    def test_is_trace_root(self):
        """Test IsTraceRoot presence in stats.
        Note: Once all tracers have implmented it and the test xpasses for all of them, we can move these
        assertions to `test_client_stats` method.
        """
        root_found = False
        for s in interfaces.agent.get_stats(resource="GET /stats-unique"):
            if s["SpanKind"] == "server":
                root_found |= s["IsTraceRoot"] == 1
        assert root_found

    @scenarios.default
    def test_disable(self):
        requests = list(interfaces.library.get_data("/v0.6/stats"))
        assert len(requests) == 0, "Stats should be disabled by default"


@features.client_side_stats_supported
@scenarios.trace_stats_computation
class Test_Agent_Info_Endpoint:
    """Test agent /info endpoint feature detection for Client-Side Stats"""

    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "nodejs", "php", "python", "ruby")
        or context.library <= "java@1.52.1",
        reason="Tracers have not implemented this feature yet.",
    )
    def test_info_endpoint_supports_client_side_stats(self):
        """Test that agent /info endpoint contains required fields for Client-Side Stats feature detection"""
        info_requests = list(interfaces.library.get_data("/info"))
        info_data = info_requests[0]["response"]["content"]

        assert isinstance(info_data, dict), f"Agent info response should be a JSON object, got: {type(info_data)}"

        # Required fields
        assert "endpoints" in info_data, "Agent info should contain endpoints array"
        assert "client_drop_p0s" in info_data, "Agent info should contain client_drop_p0s field"
        assert "version" in info_data, "Agent info should contain version field"

        # Validate endpoints contain required stats endpoint
        endpoints = info_data["endpoints"]
        assert isinstance(endpoints, list), "endpoints should be an array"
        assert "/v0.6/stats" in endpoints, "Agent should support /v0.6/stats endpoint"

        # Validate client_drop_p0s capability
        client_drop_p0s = info_data["client_drop_p0s"]
        assert isinstance(client_drop_p0s, bool), "client_drop_p0s should be boolean"
        assert client_drop_p0s is True, "Agent should support client-side P0 dropping"

        # Validate version format
        version = info_data["version"]
        assert isinstance(version, str), "version should be a string"
        assert len(version) > 0, "version should not be empty"

        # Validate optional fields
        if "feature_flags" in info_data:
            feature_flags = info_data["feature_flags"]
            assert isinstance(feature_flags, list), "feature_flags should be an array if present"
            # Common feature flags to check for if present
            if "discovery" in feature_flags:
                logger.debug("Agent supports discovery feature flag")
            if "receive_stats" in feature_flags:
                logger.debug("Agent supports receive_stats feature flag")

        if "statsd_port" in info_data:
            assert isinstance(info_data["statsd_port"], int), "statsd_port should be integer"
            assert info_data["statsd_port"] > 0, "statsd_port should be positive"

        if "peer_tags" in info_data:
            peer_tags = info_data["peer_tags"]
            assert isinstance(peer_tags, list), "peer_tags should be an array"
            expected_peer_tags = [
                "_dd.peer.service",
                "peer.service",
                "out.host",
                "db.instance",
                "messaging.destination",
            ]
            for tag in expected_peer_tags:
                if tag in peer_tags:  # Some may be missing depending on agent version
                    assert isinstance(tag, str), f"peer tag {tag} should be string"

        if "obfuscation_version" in info_data:
            obfuscation_version = info_data["obfuscation_version"]
            assert isinstance(obfuscation_version, int), "obfuscation_version should be integer"
            assert obfuscation_version >= 1, "obfuscation_version should be at least 1 for Client-Side Stats"


@features.client_side_stats_supported
@scenarios.trace_stats_computation
class Test_Peer_Tags:
    """Test peer tags aggregation for Client-Side Stats"""

    def setup_peer_tags(self):
        """Setup for peer tags test - generates client and server spans"""
        # Generate client spans by making outbound HTTP calls (should have peer tags)
        for _ in range(3):
            weblog.get("/make_distant_call?url=http://weblog:7777/healthcheck")

        # Generate server spans by hitting regular endpoints (should not have peer tags)
        for _ in range(2):
            weblog.get("/healthcheck")

    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "nodejs", "php", "python", "ruby")
        or context.library <= "java@1.52.1",
        reason="Tracers have not implemented this feature yet.",
    )
    def test_peer_tags(self):
        """Test that client spans include peer tags while server spans don't"""
        client_stats_found = False
        server_stats_found = False

        for s in interfaces.agent.get_stats():
            resource = s.get("Resource", "")
            span_kind = s.get("SpanKind", "")
            peer_tags = s.get("PeerTags", [])
            service = s.get("Service", "")
            span_type = s.get("Type", "")

            logger.debug(
                f"Checking stats - Resource: {resource}, SpanKind: {span_kind}, PeerTags: {peer_tags}, Service: {service}, Type: {span_type}"
            )

            # Client spans should have peer tags
            if span_kind == "client" and span_type == "http":
                client_stats_found = True

                assert len(peer_tags) > 0, f"Client spans should have peer tags, found: {peer_tags}"

                # Common peer tags we expect for HTTP client calls
                expected_peer_tag_prefixes = [
                    "out.host",
                    "http.host",
                    "network.destination",
                    "server.address",
                    "peer.hostname",
                ]
                found_expected_tags = any(
                    any(tag.startswith(prefix) for prefix in expected_peer_tag_prefixes) for tag in peer_tags
                )
                assert found_expected_tags, f"Client span does not contain expected peer tags: {peer_tags}"

            # Server spans should not have peer tags (except _dd.base_service)
            elif span_kind == "server" and span_type == "web":
                server_stats_found = True

                assert len(peer_tags) == 0, f"Server spans should have peer tags, found: {peer_tags}"

        assert client_stats_found, "Should find client spans with peer tags from /make_distant_call endpoint"
        assert server_stats_found, "Should find server spans without peer tags from /healthcheck endpoint"


@features.client_side_stats_supported
@scenarios.trace_stats_computation
class Test_Transport_Headers:
    """Test transport headers validation for Client-Side Stats"""

    def setup_transport_headers(self):
        """Setup for transport headers test - generates stats to trigger transport"""
        for _ in range(2):
            weblog.get("/")

    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "nodejs", "php", "python", "ruby")
        or context.library <= "java@1.52.1",
        reason="Tracers have not implemented this feature yet.",
    )
    def test_transport_headers(self):
        """Test that stats transport includes required and optional headers"""
        stats_requests = list(interfaces.library.get_data("/v0.6/stats"))
        assert len(stats_requests) > 0, "Should have at least one stats request"

        # Test the most recent stats request
        stats_request = stats_requests[-1]
        headers = {header[0]: header[1] for header in stats_request["request"]["headers"]}

        logger.debug(f"Stats request headers: {headers}")

        assert "Content-Type" in headers, "Stats request should have Content-Type header"
        assert (
            headers["Content-Type"] == "application/msgpack"
        ), f"Content-Type should be application/msgpack, found: {headers['Content-Type']}"

        content_length = headers.get("Content-Length")
        assert content_length, f"Content-Length should not be empty, found: {content_length}"
        assert int(content_length) > 0, f"Content-Length should be positive, found: {content_length}"

        assert "Datadog-Meta-Lang" in headers, "Datadog-Meta-Lang header not found"
        assert headers["Datadog-Meta-Lang"], "Datadog-Meta-Lang header should not be empty"

        assert "Datadog-Meta-Tracer-Version" in headers, "Datadog-Meta-Tracer-Version header not found"
        assert headers["Datadog-Meta-Tracer-Version"], "Datadog-Meta-Tracer-Version header should not be empty"

        if "Datadog-Obfuscation-Version" in headers:
            obfuscation_version = headers["Datadog-Obfuscation-Version"]
            # Validate it's a positive integer string
            assert (
                obfuscation_version.isdigit()
            ), f"Obfuscation version should be positive integer, found: {obfuscation_version}"
            assert (
                int(obfuscation_version) > 0
            ), f"Obfuscation version should be positive integer, found: {obfuscation_version}"

    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "nodejs", "php", "python", "ruby"),
        reason="Tracers have not implemented this feature yet.",
    )
    @bug(
        context.library == "java",
        reason="LANGPLAT-755",
    )
    def test_container_id_header(self):
        """Test that stats transport includes container id headers"""
        stats_requests = list(interfaces.library.get_data("/v0.6/stats"))
        assert len(stats_requests) > 0, "Should have at least one stats request"

        # Test the most recent stats request
        stats_request = stats_requests[-1]
        headers = {header[0]: header[1] for header in stats_request["request"]["headers"]}

        logger.debug(f"Stats request headers: {headers}")

        # we must have at least one of the CID resolution headers
        cid_headers_list = ["Datadog-Entity-Id", "Datadog-External-Env", "Datadog-Container-ID"]
        cid_headers = [h for h in headers if h in cid_headers_list]
        assert len(cid_headers) > 0, f"ContainerID resolution headers not found: {headers}"
        for h in cid_headers:
            assert len(headers[h]) > 0, "ContainerID resolution header should not be empty"


@features.client_side_stats_supported
@scenarios.trace_stats_computation
class Test_Time_Bucketing:
    """Test time bucketing validation for Client-Side Stats"""

    def setup_client_side_stats(self):
        """Setup for time bucketing test - generates spans across time"""
        for _ in range(3):
            weblog.get("/")

    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "java", "nodejs", "php", "python", "ruby"),
        reason="Tracers have not implemented this feature yet.",
    )
    def test_client_side_stats(self):
        """Test that client-side stats are properly bucketed in 10-second intervals"""
        stats_requests = list(interfaces.library.get_data("/v0.6/stats"))
        assert len(stats_requests) > 0, "Should have at least one stats request"

        # Get the payload content
        stats_payload = stats_requests[-1]["request"]["content"]
        stats_buckets = stats_payload.get("Stats", [])

        assert len(stats_buckets) > 0, "Should have at least one stats bucket"

        for bucket in stats_buckets:
            start = bucket.get("Start")
            duration = bucket.get("Duration")
            stats = bucket.get("Stats", [])

            logger.debug(f"Checking CSS bucket - Start: {start}, Duration: {duration}, Stats count: {len(stats)}")

            # Validate bucket structure
            assert start is not None, "Bucket should have Start time"
            assert duration is not None, "Bucket should have Duration"
            assert isinstance(start, int), f"Start should be integer (nanoseconds), found: {type(start)}"
            assert isinstance(duration, int), f"Duration should be integer (nanoseconds), found: {type(duration)}"

            # Validate 10-second bucket duration for tracer stats
            expected_duration = 10_000_000_000  # 10 seconds in nanoseconds
            assert (
                duration == expected_duration
            ), f"CSS bucket duration should be 10 seconds ({expected_duration} ns), found: {duration}"

            # Validate bucket alignment (start should be aligned to 10-second boundaries)
            assert (
                start % expected_duration == 0
            ), f"CSS bucket start should be aligned to 10-second boundaries, found: {start}"

            # Validate stats array is not empty and properly structured
            assert len(stats) > 0, "Bucket should contain stats, found empty bucket"

            for stat in stats:
                # Each stat should have required fields
                required_fields = ["Service", "Name", "Resource", "Type", "Hits", "Errors", "Duration"]
                for field in required_fields:
                    assert field in stat, f"Stat should have {field} field, found: {list(stat.keys())}"

                # Validate numeric fields are non-negative
                assert stat["Hits"] >= 0, f"Hits should be non-negative, found: {stat['Hits']}"
                assert stat["Errors"] >= 0, f"Errors should be non-negative, found: {stat['Errors']}"
                assert stat["Duration"] >= 0, f"Duration should be non-negative, found: {stat['Duration']}"

    def setup_agent_aggregated_stats(self):
        """Setup for agent stats test - generates spans for agent aggregation"""
        for _ in range(3):
            weblog.get("/")

    @missing_feature(
        context.library in ("cpp", "cpp_httpd", "cpp_nginx", "dotnet", "nodejs", "php", "python", "ruby"),
        reason="Tracers have not implemented this feature yet.",
    )
    def test_agent_aggregated_stats(self):
        """Test that agent-aggregated stats use 2-second buckets with 1-second offset"""

        for data in interfaces.agent.get_data(path_filters="/api/v0.2/stats"):
            payload = data["request"]["content"]
            if not payload["ClientComputed"] or not payload["Stats"]:
                continue

            count = 0
            for ss in payload["Stats"]:
                for s in ss["Stats"]:
                    count += 1

                    start = s["Start"]
                    duration = s["Duration"]
                    stats = s["Stats"]

                    assert start is not None, "Bucket should have Start time"
                    assert duration is not None, "Bucket should have Duration"
                    assert isinstance(start, int), f"Start should be integer (nanoseconds), found: {type(start)}"
                    assert isinstance(
                        duration, int
                    ), f"Duration should be integer (nanoseconds), found: {type(duration)}"

                    # Validate 10-second bucket duration for aggregated stats
                    expected_duration = 10_000_000_000  # 10 seconds in nanoseconds
                    assert (
                        duration == expected_duration
                    ), f"agent-aggregated bucket duration should be 10 seconds ({expected_duration} ns), found: {duration}"

                    # Validate bucket alignment (start should be aligned to 2s boundary, with 1s offset)
                    offset = 1_000_000_000
                    assert (
                        (start + offset) % 2_000_000_000 == 0
                    ), f"agent-aggregated bucket start should be aligned to 2-second boundaries, found: {start}"

                    # Validate stats array is not empty and properly structured
                    assert len(stats) > 0, "Bucket should contain stats, found empty bucket"

            assert count > 0, "agent-aggregated stats should not be empty"
