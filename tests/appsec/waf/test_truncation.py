import json
from utils import weblog, rfc, features, interfaces


def create_nested_object(n, obj):
    if n > 0:
        return {"a": create_nested_object(n - 1, obj)}
    return obj


@rfc("https://docs.google.com/document/d/1D4hkC0jwwUyeo0hEQgyKP54kM1LZU98GL8MaP60tQrA")
@features.appsec_truncation_action
class Test_Truncation:
    """Test WAF truncation"""

    def _find_series(self, request_type, namespace, metrics):
        series = []
        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != request_type:
                continue
            fallback_namespace = content["payload"].get("namespace")
            for serie in content["payload"]["series"]:
                computed_namespace = serie.get("namespace", fallback_namespace)
                if computed_namespace == namespace and serie["metric"] in metrics:
                    series.append(serie)
        return series

    def setup_truncation(self):
        # Create complex data
        long_value = "testattack" * 500
        large_object = {}
        for i in range(300):
            large_object[f"key{i}"] = f"value{i}"
        deep_object = create_nested_object(25, {"value": "a"})

        complex_payload = {"deepObject": deep_object, "longValue": long_value, "largeObject": large_object}

        self.req = weblog.post(
            "/waf",
            headers={"Content-Type": "application/json"},
            data=json.dumps(complex_payload),
        )

    def test_truncation(self):
        span = interfaces.library.get_root_span(self.req)
        metrics = span.get("metrics")
        assert metrics, "Expected metrics"

        assert int(metrics["_dd.appsec.truncated.string_length"]) == 5000
        assert int(metrics["_dd.appsec.truncated.container_size"]) == 300
        assert int(metrics["_dd.appsec.truncated.container_depth"]) == 20

        waf_requests_series = self._find_series("generate-metrics", "appsec", ["waf.requests"])
        has_input_truncated = any("input_truncated:true" in series["tags"] for series in waf_requests_series)
        assert has_input_truncated, "Expected at least one serie to have input_truncated:true tag"

        all_have_input_truncated_tag = all(
            "input_truncated:true" in series["tags"] or "input_truncated:false" in series["tags"]
            for series in waf_requests_series
        )
        assert all_have_input_truncated_tag, "Expected all series to have input_truncated tag"

        count_series = self._find_series("generate-metrics", "appsec", ["waf.input_truncated"])
        input_truncated = count_series[0] if count_series else None

        assert input_truncated is not None, "No telemetry data received for metric appsec.waf.input_truncated"

        assert input_truncated["type"] == "count"
        assert "truncation_reason:7" in input_truncated["tags"]

        distribution_series = self._find_series("distributions", "appsec", ["waf.truncated_value_size"])

        assert (
            len(distribution_series) == 3
        ), "Not all telemetry data received for metric appsec.waf.truncated_value_size"

        long_string = [d for d in distribution_series if "truncation_reason:1" in d["tags"]]
        assert long_string, "No distribution for long string truncation"

        large_container = [d for d in distribution_series if "truncation_reason:2" in d["tags"]]
        assert large_container, "No distribution for large container truncation"

        deep_container = [d for d in distribution_series if "truncation_reason:4" in d["tags"]]
        assert deep_container, "No distribution for deep container truncation"
