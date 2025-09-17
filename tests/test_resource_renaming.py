from utils import scenarios, weblog, interfaces, features


@features.resource_renaming
@scenarios.trace_resource_renaming
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

    def test_http_endpoint_basic(self):
        """Test basic endpoint extraction without parameters"""
        spans = interfaces.library.get_spans(self.r_basic)
        for _, _, span in spans:
            if "http.endpoint" in span.get("meta", {}):
                assert span["meta"]["http.endpoint"] == "/resource_renaming/some/url"

        # Test integer parameter replacement
        spans = interfaces.library.get_spans(self.r_param_int)
        for _, _, span in spans:
            endpoint = span["meta"]["http.endpoint"]
            assert endpoint == "/resource_renaming/int/{param:int}"

        # Test integer id parameter replacement
        spans = interfaces.library.get_spans(self.r_param_int_id)
        for _, _, span in spans:
            endpoint = span["meta"]["http.endpoint"]
            assert endpoint == "/resource_renaming/int_id/{param:int_id}"

        # Test hex parameter replacement
        spans = interfaces.library.get_spans(self.r_param_hex)
        for _, _, span in spans:
            endpoint = span["meta"]["http.endpoint"]
            assert endpoint == "/resource_renaming/hex/{param:hex}"

        # Test hex id parameter replacement
        spans = interfaces.library.get_spans(self.r_param_hex_id)
        for _, _, span in spans:
            endpoint = span["meta"]["http.endpoint"]
            assert endpoint == "/resource_renaming/hex_id/{param:hex_id}"

        # Test string parameter replacement
        spans = interfaces.library.get_spans(self.r_param_str)
        for _, _, span in spans:
            endpoint = span["meta"]["http.endpoint"]
            assert endpoint == "/resource_renaming/files/{param:str}"

    def setup_http_endpoint_edge_cases(self):
        """Setup requests for edge case testing"""
        self.r_root = weblog.get("/")
        self.r_long_path = weblog.get("/resource_renaming/a/b/c/d/e/f/g/h/i/j/k/l/m")
        self.r_empty_segments = weblog.get("/resource_renaming//double//slash")

    def test_http_endpoint_edge_cases(self):
        """Test that edge cases are handled correctly"""
        spans = interfaces.library.get_spans(self.r_root)

        for _, _, span in spans:
            endpoint = span["meta"]["http.endpoint"]
            assert endpoint == "/"

        spans = interfaces.library.get_spans(self.r_long_path)
        for _, _, span in spans:
            endpoint = span["meta"]["http.endpoint"]
            assert len(endpoint) > 0
            assert endpoint == "/resource_renaming/a/b/c/d/e/f/g"

        spans = interfaces.library.get_spans(self.r_empty_segments)
        for _, _, span in spans:
            endpoint = span["meta"]["http.endpoint"]
            assert endpoint == "/resource_renaming/double/slash"


@features.resource_renaming
@scenarios.trace_resource_renaming
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
