from utils import interfaces, released, rfc, weblog, scenarios, context


TELEMETRY_REQUEST_TYPE_GENERATE_METRICS = "generate-metrics"
TELEMETRY_REQUEST_TYPE_DISTRIBUTIONS = "distributions"


def _validate_headers(headers, request_type):
    """https://github.com/DataDog/instrumentation-telemetry-api-docs/blob/main/GeneratedDocumentation/ApiDocs/v2/how-to-use.md
    """
    # empty value means we don't care about the content, but we want to check the key exists
    expected_headers = {
        "Content-type": "application/json",
        "DD-Telemetry-API-Version": "v1",
        "DD-Telemetry-Request-Type": request_type,
        "DD-Client-Library-Language": context.library,
        "DD-Client-Library-Version": "",
        "DD-Agent-Env": "system-tests",
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


def _validate_generate_metrics_headers(headers):
    _validate_headers(headers, TELEMETRY_REQUEST_TYPE_GENERATE_METRICS)


def _validate_distributions_headers(headers):
    _validate_headers(headers, TELEMETRY_REQUEST_TYPE_DISTRIBUTIONS)


def _validate_tags(payload_tags, expected_tags, metric_name):
    for tag in payload_tags:
        tag_key, tag_value = tag.split(":")

        if expected_tags.get(tag_key) is not None:
            expected_tag = expected_tags.pop(tag_key)
            if expected_tag != "":
                assert tag_value.lower() == expected_tag, "Metric %s Tag %s. Expected %s. get %s" % (
                    metric_name,
                    tag_key,
                    expected_tag,
                    tag_value,
                )
            else:
                assert expected_tag is not None, f"Empty `{expected_tag}` tag"

    if len(expected_tags) > 0:
        raise AssertionError(f"Metric %s Tags %s not found" % (metric_name, [metric for metric in expected_tags]))


def _validate_generate_metrics_metrics(payload):
    """https://github.com/DataDog/instrumentation-telemetry-api-docs/blob/main/GeneratedDocumentation/ApiDocs/v2/SchemaDocumentation/Schemas/metric_data.md
    """
    # CAVEAT: each library could have different metrics result. If you get an error ping in slack
    expected_common_tags = [
        {
            "waf_version": "1.6.1",
            "event_rules_version": context.appsec_rules_version,
            "rule_triggered": "false",
            "request_blocked": "false",
        },
        {
            "waf_version": "1.6.1",
            "event_rules_version": context.appsec_rules_version,
            "rule_triggered": "true",
            "request_blocked": "false",
        },
    ]
    expected_metrics = {
        "event_rules.loaded": {"type": "count", "num_points": 1, "point": 134.0, "tags": {}, "found": 0},
        "waf.requests": {"type": "count", "num_points": 1, "point": 1.0, "tags": {}, "found": 0},
    }
    assert payload["namespace"] == "appsec"
    assert len(payload["series"]) == 4

    for serie in payload["series"]:
        if expected_metrics.get(serie["metric"]):
            expected_metric = expected_metrics.get(serie["metric"])
            assert serie["common"] is True
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
            _validate_tags(
                serie["tags"],
                dict(expected_common_tags[expected_metric["found"]], **expected_metric["tags"]),
                serie["metric"],
            )
            expected_metric["found"] += 1
    if not all(metric["found"] > 0 for _, metric in expected_metrics.items()):
        raise AssertionError(
            f"Metrics %s not found in payload"
            % [(metric, value["found"]) for metric, value in expected_metrics.items()]
        )


def _validate_distributions_metrics(payload):
    """https://github.com/DataDog/instrumentation-telemetry-api-docs/blob/main/GeneratedDocumentation/ApiDocs/v2/SchemaDocumentation/Schemas/metric_data.md
    """
    # CAVEAT: each library could have different metrics result. If you get an error ping in slack
    expected_common_tags = [
        {
            "waf_version": "",
            "event_rules_version": context.appsec_rules_version,
            "rule_triggered": "false",
            "request_blocked": "false",
        },
        {
            "waf_version": "",
            "event_rules_version": context.appsec_rules_version,
            "rule_triggered": "true",
            "request_blocked": "false",
        },
    ]
    expected_metrics = {
        "waf.duration": {"num_points": 1, "point": 0.01, "tags": {}, "found": 0},
        "waf.duration_ext": {"num_points": 1, "point": 0.01, "tags": {}, "found": 0},
    }
    assert payload["namespace"] == "appsec"
    assert len(payload["series"]) == 4

    for serie in payload["series"]:
        if expected_metrics.get(serie["metric"]):
            expected_metric = expected_metrics.get(serie["metric"])
            assert len(serie["points"]) == expected_metric["num_points"], "Metric %s. Expected %s point. get %s" % (
                serie["metric"],
                expected_metric["num_points"],
                serie["points"],
            )
            assert serie["points"][0] >= expected_metric["point"], "Metric %s. Expected %s. get %s" % (
                serie["metric"],
                expected_metric["point"],
                serie["points"],
            )
            _validate_tags(
                serie["tags"],
                dict(expected_common_tags[expected_metric["found"]], **expected_metric["tags"]),
                serie["metric"],
            )
            expected_metric["found"] += 1

    if not all(metric["found"] > 0 for _, metric in expected_metrics.items()):
        raise AssertionError(
            f"Metrics %s not found in payload"
            % [(metric, value["found"]) for metric, value in expected_metrics.items()]
        )


@rfc("https://docs.google.com/document/d/1qBDsS_ZKeov226CPx2DneolxaARd66hUJJ5Lh9wjhlE")
@released(python="?", cpp="?", golang="?", java="1.12.0", dotnet="?", nodejs="?", php="?", ruby="?")
@scenarios.appsec_waf_telemetry
class Test_TelemetryMetricsTriggered:
    """Test instrumentation telemetry metrics, type of metrics generate-metrics"""

    generate_metrics_requests = False

    def setup_telemetry_metrics_request_analyzed(self):
        """AppSec catches attacks in URL query key"""
        self.r = weblog.get("/myadmin")

    def test_telemetry_metrics_request_analyzed(self):
        """Test that telemetry requests are successful"""

        def validator(data):
            assert data["response"]["status_code"] == 202
            if data["request"]["content"].get("request_type") == TELEMETRY_REQUEST_TYPE_DISTRIBUTIONS:
                self.generate_metrics_requests = True
                _validate_distributions_headers(data["request"]["headers"])
                _validate_distributions_metrics(data["request"]["content"]["payload"])
            if data["request"]["content"].get("request_type") == TELEMETRY_REQUEST_TYPE_GENERATE_METRICS:
                self.generate_metrics_requests = True
                _validate_generate_metrics_headers(data["request"]["headers"])
                _validate_generate_metrics_metrics(data["request"]["content"]["payload"])

        interfaces.library.validate_telemetry(validator, success_by_default=True)
