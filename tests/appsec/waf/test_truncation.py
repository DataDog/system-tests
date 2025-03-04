import json
from utils import scenarios, weblog, rfc, features, interfaces

def create_nested_object(n, obj):
    if n > 0:
        return {"a": create_nested_object(n - 1, obj)}
    return obj

@rfc("https://docs.google.com/document/d/1D4hkC0jwwUyeo0hEQgyKP54kM1LZU98GL8MaP60tQrA")
@scenarios.appsec_blocking
@features.appsec_truncation_action
class Test_Truncation:
    """Test WAF truncation"""

    def setup_truncation(self):
      # Create complex data
      long_value = "testattack" * 500
      large_object = {}
      for i in range(300):
          large_object[f"key{i}"] = f"value{i}"
      deep_object = create_nested_object(25, {"value": "a"})

      complex_payload = {
          "deepObject": deep_object,
          "longValue": long_value,
          "largeObject": large_object
      }

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
