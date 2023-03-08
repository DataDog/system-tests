from utils import interfaces, released, rfc, weblog, scenarios, context
from utils.tools import logger

TELEMETRY_REQUEST_TYPE_GENERATE_METRICS = "generate-metrics"


def _validate_headers(headers):
    """https://github.com/DataDog/instrumentation-telemetry-api-docs/blob/main/GeneratedDocumentation/ApiDocs/v2/how-to-use.md
    """
    # empty value means we don't care about the content, but we want to check the key exists
    expected_headers = {
        "Content-type": "application/json",
        "DD-Telemetry-API-Version": "v2",
        "DD-Telemetry-Request-Type": TELEMETRY_REQUEST_TYPE_GENERATE_METRICS,
        "DD-Client-Library-Language": context.library,
        "DD-Client-Library-Version": "",
        "DD-Agent-Env": "",
        "DD-Agent-Hostname": "",
    }

    for key, value in headers:
        if expected_headers.get(key) is not None:
            expected_value = expected_headers.pop(key)
            if expected_value != "":
                assert value == expected_value
            else:
                assert value is not None, f"Empty `{key}` header"

    if len(expected_headers) > 0:
        raise AssertionError(
            "Headers %s not found in payload headers: %s" % ([header for header in expected_headers], headers)
        )


def _validate_metrics(payload):
    """https://github.com/DataDog/instrumentation-telemetry-api-docs/blob/main/GeneratedDocumentation/ApiDocs/v2/SchemaDocumentation/Schemas/metric_data.md
    """
    # CAVEAT: each library could have different metrics result. If you get an error ping in slack
    expected_metrics = {
        "event_rules.loaded": {"type": "count", "num_points": 1, "point": 134.0},
        # TODO: validate distributions payload type
        #  "waf.duration": {"type": "count", "num_points": 2, "point": 100.0},
        #  "waf.duration_ext": {"type": "count", "num_points": 2, "point": 100.0},
    }
    assert payload["namespace"] == "appsec"
    assert len(payload["series"]) > 0

    for serie in payload["series"]:
        if expected_metrics.get(serie["metric"]):
            expected_metric = expected_metrics.pop(serie["metric"])
            assert serie["type"] == expected_metric["type"], "Metric %s. Expected %s. get %s" % (
                serie["metric"],
                expected_metric["type"],
                serie["type"],
            )
            assert len(serie["points"]) == expected_metric["num_points"], "Metric %s. Expected %s point. get %s" % (
                serie["metric"],
                expected_metric["num_points"],
                serie["points"],
            )
            assert serie["points"][0][1] >= expected_metric["point"], "Metric %s. Expected %s. get %s" % (
                serie["metric"],
                expected_metric["point"],
                serie["points"],
            )

    if len(expected_metrics) > 0:
        raise AssertionError(f"Metrics %s not found in payload" % [metric for metric in expected_metrics])


@rfc("https://docs.google.com/document/d/1qBDsS_ZKeov226CPx2DneolxaARd66hUJJ5Lh9wjhlE")
@released(python="?", cpp="?", golang="?", java="?", dotnet="?", nodejs="?", php="?", ruby="?")
@scenarios.appsec_waf_telemetry
class Test_TelemetryMetrics:
    """Test instrumentation telemetry metrics, type of metrics generate-metrics"""

    generate_metrics_requests = False

    def setup_telemetry_metrics_one_request(self):
        """AppSec catches attacks in URL query key"""
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_telemetry_metrics_one_request(self):
        """Test that telemetry requests are successful"""

        def validator(data):
            logger.warning(data)
            if data["request"]["content"].get("request_type") == TELEMETRY_REQUEST_TYPE_GENERATE_METRICS:
                self.generate_metrics_requests = True
                assert data["response"]["status_code"] == 202
                _validate_headers(data["request"]["headers"])
                _validate_metrics(data["request"]["content"]["payload"])
                return True
            return False

        interfaces.library.validate_telemetry(validator)
