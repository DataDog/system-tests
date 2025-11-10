from utils import bug, scenarios, weblog, interfaces, features
from utils._weblog import HttpResponse


def get_endpoint_tag(response: HttpResponse) -> str | None:
    spans = interfaces.library.get_spans(response)
    for _, _, span in spans:
        if "http.endpoint" in span.get("meta", {}):
            return span["meta"]["http.endpoint"]
    return None


@features.resource_renaming
@scenarios.tracing_config_nondefault_3
@scenarios.appsec_blocking
class Test_Resource_Renaming_HTTP_Endpoint_Tag:
    """Test the correct extraction of the http.endpoint tag"""

    def setup_http_endpoint_basic(self):
        """Setup basic endpoint extraction tests"""
        self.r_basic = weblog.get("/resource_renaming/some/url")
        self.r_param_int = weblog.get("/resource_renaming/int/123")
        self.r_param_int_id = weblog.get("/resource_renaming/int_id/123-456.678")
        self.r_param_hex = weblog.get("/resource_renaming/hex/abc123")
        self.r_param_hex_id = weblog.get("/resource_renaming/hex_id/abc123-abc123")
        self.r_param_str = weblog.get("/resource_renaming/files/very-long-filename-with-special-chars")
        self.r_param_str_2 = weblog.get("/resource_renaming/files/test%40%2B%3D")

    def test_http_endpoint_basic(self):
        """Test basic endpoint extraction without parameters"""
        assert get_endpoint_tag(self.r_basic) == "/resource_renaming/some/url"
        assert get_endpoint_tag(self.r_param_int) == "/resource_renaming/int/{param:int}"
        assert get_endpoint_tag(self.r_param_int_id) == "/resource_renaming/int_id/{param:int_id}"
        assert get_endpoint_tag(self.r_param_hex) == "/resource_renaming/hex/{param:hex}"
        assert get_endpoint_tag(self.r_param_hex_id) == "/resource_renaming/hex_id/{param:hex_id}"
        assert get_endpoint_tag(self.r_param_str) == "/resource_renaming/files/{param:str}"
        assert get_endpoint_tag(self.r_param_str_2) == "/resource_renaming/files/{param:str}"

    def setup_http_endpoint_edge_cases(self):
        """Setup requests for edge case testing"""
        self.r_root = weblog.get("/")
        self.r_long_path = weblog.get("/resource_renaming/a/b/c/d/e/f/g/h/i/j/k/l/m")
        self.r_empty_segments = weblog.get("/resource_renaming//double//slash")

    def test_http_endpoint_edge_cases(self):
        """Test that edge cases are handled correctly"""
        assert get_endpoint_tag(self.r_root) == "/"
        assert get_endpoint_tag(self.r_long_path) == "/resource_renaming/a/b/c/d/e/f/g"
        assert get_endpoint_tag(self.r_empty_segments) == "/resource_renaming/double/slash"


@features.resource_renaming
@scenarios.tracing_config_nondefault_3
@scenarios.appsec_blocking
class Test_Resource_Renaming_Stats_Aggregation_Keys:
    """Test that stats aggregation includes method and endpoint in aggregation keys"""

    def setup_stats_aggregation_with_method_and_endpoint(self):
        """Generate multiple requests to create stats"""
        # Generate multiple requests to the same endpoint for aggregation
        self.requests = []
        for _ in range(5):
            self.requests.append(weblog.get("/resource_renaming/api/users/123"))
        for _ in range(3):
            self.requests.append(weblog.get("/resource_renaming/api/posts/456"))

    @bug(library="python", reason="APMSP-2359")  # trace exporter uses a wrong fieldname
    def test_stats_aggregation_with_method_and_endpoint(self):
        """Test that stats are aggregated by method and endpoint"""
        stats_points = []
        for stats_data in interfaces.library.get_data("/v0.6/stats"):
            stats = stats_data.get("request", {}).get("content", {}).get("Stats", [])
            for stat_bucket in stats:
                stats_points.extend(stat_bucket.get("Stats", []))

        # Expected hits based on setup method
        expected_hits = {
            ("GET", "/resource_renaming/api/users/{param:int}"): 5,
            ("GET", "/resource_renaming/api/posts/{param:int}"): 3,
        }

        # Collect actual hits from stats points
        actual_hits = {}
        for point in stats_points:
            method = point.get("HTTPMethod", "")
            endpoint = point.get("HTTPEndpoint", "")
            hits = point.get("Hits", 0)

            if (method, endpoint) in expected_hits:
                actual_hits[(method, endpoint)] = hits

        # Verify that the hits match expectations
        for (method, endpoint), expected_count in expected_hits.items():
            assert (method, endpoint) in actual_hits, f"Missing stats for {method} {endpoint}"
            actual_count = actual_hits[(method, endpoint)]
            assert (
                actual_count == expected_count
            ), f"Expected {expected_count} hits for {method} {endpoint}, got {actual_count}"
