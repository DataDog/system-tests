from utils import interfaces, released, rfc, weblog, coverage, scenario, context
from utils.tools import logger

TELEMETRY_REQUEST_TYPE_GENERATE_METRICS = "generate-metrics"


def _validate_headers(headers, language):
    """https://github.com/DataDog/instrumentation-telemetry-api-docs/blob/main/GeneratedDocumentation/ApiDocs/v2/how-to-use.md
    """
    expected_headers = {
        "Content-type": "application/json",
        "DD-Telemetry-API-Version": "v1",
        "DD-Telemetry-Request-Type": TELEMETRY_REQUEST_TYPE_GENERATE_METRICS,
        "DD-Client-Library-Language": language,
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


def _validate_metrics(payload, language):
    """https://github.com/DataDog/instrumentation-telemetry-api-docs/blob/main/GeneratedDocumentation/ApiDocs/v2/SchemaDocumentation/Schemas/metric_data.md
    """
    expected_metrics = {
        "dd.app_telemetry.appsec.event_rules.loaded": {"type": "count", "num_points": 1, "point": 134.0},
        "dd.app_telemetry.appsec.event_rules.error_count": {"type": "count", "num_points": 1, "point": 0.0},
        "dd.app_telemetry.appsec.waf.duration": {"type": "count", "num_points": 1, "point": 100.0},
        "dd.app_telemetry.appsec.waf.duration_ext": {"type": "count", "num_points": 1, "point": 100.0},
    }
    assert payload["namespace"] == "appsec"
    assert len(payload["series"]) > 0

    for serie in payload["series"]:
        if expected_metrics.get(serie["name"]):
            expected_metric = expected_metrics.pop(serie["name"])
            assert serie["type"] == expected_metric["type"]
            assert len(serie["points"]) == expected_metric["num_points"]
            assert serie["points"][0][1] >= expected_metric["point"]

    if len(expected_metrics) > 0:
        raise AssertionError(f"Metrics %s not found in payload" % [metric for metric in expected_metrics])


@rfc("https://docs.google.com/document/d/1qBDsS_ZKeov226CPx2DneolxaARd66hUJJ5Lh9wjhlE")
@released(python="?", cpp="?", golang="?", java="?", dotnet="?", nodejs="?", php="?", ruby="?")
@scenario("APPSEC_WAF_TELEMETRY")
class Test_TelemetryMetrics:
    """Test instrumentation telemetry metrics, type of metrics generate-metrics"""

    generate_metrics_requests = False

    def setup_query_key(self):
        """AppSec catches attacks in URL query key"""
        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

    def test_status_ok(self):
        """Test that telemetry requests are successful"""

        def validator(data):
            try:
                # logger.info(data)
                if data["request"]["content"].get("request_type") == TELEMETRY_REQUEST_TYPE_GENERATE_METRICS:
                    self.generate_metrics_requests = True
                    assert data["response"]["status_code"] == 202
                    _validate_headers(data["request"]["headers"], context.library)
                    _validate_metrics(data["request"]["content"]["payload"], context.library)
                    return True
            except Exception as e:
                logger.error(str(e), exc_info=True)
                raise
            return False

        interfaces.library.validate_telemetry(validator, success_by_default=False)

        assert self.generate_metrics_requests, f"No metrics {TELEMETRY_REQUEST_TYPE_GENERATE_METRICS} type detected"
