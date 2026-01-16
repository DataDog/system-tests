# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, interfaces, rfc, scenarios, weblog, features

from tests.appsec.api_security.test_schemas import get_schema


def _extract_telemetry_metrics(datas: list[dict]) -> list[dict]:
    res = [data["request"]["content"] for data in datas]
    metrics = []
    for r in res:
        if r.get("request_type") == "generate-metrics":
            metrics.extend(r["payload"]["series"])
    return [m for m in metrics if m["metric"].startswith("api_security")]


FRAMEWORKS = {
    "python": {
        "flask-poc": "flask",
        "uwsgi-poc": "flask",
        "uds-flask": "flask",
        "django-poc": "django",
        "django-py3.13": "django",
        "python3.12": "django",
        "fastapi": "fastapi",
    },
    "golang": {
        "chi": "github.com/go-chi/chi/v5",
        "echo": "github.com/labstack/echo/v4",
        "gin": "github.com/gin-gonic/gin",
        "net-http": "net/http",
        "net-http-orchestrion": "net/http",
        "uds-echo": "github.com/labstack/echo/v4",
    },
}


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_API_Security_Telemetry_Metric:
    """Test API Security - Telemetry Metric
    Verify that api_security.request.schema telemetry metric is correctly generated
    Verify that api_security.missing_routes telemetry metric is not generated for requests with 404 or blocked requests
    """

    def setup_shema_metric(self):
        # normal request that must generate schema telemetry
        self.request_1 = weblog.get("/tag_value/api_match_AS001/200")
        # blocked request, that may generate schema telemetry
        self.request_2 = weblog.get("/waf", headers={"User-Agent": "dd-test-scanner-log-block"})
        # request with 404 response, that must not generate schema telemetry
        self.request_3 = weblog.get(
            "/wafwaf"
        )  # non blocking request to ensure both blocked and non-blocked are present
        # blocked request on missing endpoint, that must not generate schema telemetry
        self.request_4 = weblog.get("/waf404", headers={"User-Agent": "dd-test-scanner-log-block"})

    def test_shema_metric(self):
        """Can provide request header schema"""
        schema = get_schema(self.request_1, "req.headers")
        assert self.request_1.status_code == 200
        assert self.request_2.status_code == 403
        assert self.request_3.status_code == 404
        assert self.request_4.status_code == 403
        assert schema
        assert isinstance(schema, list)
        for parameter_name in ("accept-encoding", "host", "user-agent"):
            assert parameter_name in schema[0]
            assert isinstance(schema[0][parameter_name], list)
        datas = _extract_telemetry_metrics(list(interfaces.library.get_telemetry_data(flatten_message_batches=True)))
        # at least on schema computed
        assert any(metric_data["metric"] == "api_security.request.schema" for metric_data in datas), (
            "api_security.request.schema metric not found in telemetry metrics"
        )
        # no missing routes should be generated
        assert all(
            metric_data["metric"] in ["api_security.request.schema", "api_security.request.no_schema"]
            for metric_data in datas
        ), "Only api_security.request.schema metrics should be present, no missing routes should be generated"
        # check all metrics have correct tags
        for m in datas:
            metric_data = m
            assert metric_data["metric"] == "api_security.request.schema"
            assert metric_data["type"] == "count"
            assert metric_data["tags"] == [
                f"framework:{FRAMEWORKS.get(context.library.name, {}).get(context.weblog_variant, context.weblog_variant)}"
            ], f"framework tag unknown for {context.library.name} {context.weblog_variant}"
