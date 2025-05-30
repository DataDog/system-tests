# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenarios, rfc, features, bug, context


@rfc("https://docs.google.com/document/d/1indvMPy4RSFeEurxssXMHUfmw6BlCexqJD_IVM6Vw9w")
@features.appsec_collect_request_body
@scenarios.appsec_rasp
class Test_ExtendedRequestBodyCollection:
    @staticmethod
    def assert_feature_is_enabled(response) -> None:
        assert response.status_code == 403
        expected_http_value = "http://169.254.169.254"
        if context.library == "nodejs":
            expected_http_value += "/"

        interfaces.library.assert_rasp_attack(
            response,
            "rasp-934-100",
            {
                "resource": {
                    "address": "server.io.net.url",
                    "value": expected_http_value,
                },
                "params": {
                    "address": "server.request.body",
                    "value": "169.254.169.254",
                },
            },
        )
        span = interfaces.library.get_root_span(request=response)
        meta_struct = span.get("meta_struct", {})
        body = meta_struct.get("http.request.body")
        assert body is not None
        assert body.get("domain") == "169.254.169.254"

    def setup_feature_is_enabled(self):
        self.check_r = weblog.post("/rasp/ssrf", data={"domain": "169.254.169.254"})

    def setup_if_rasp_event_collect_request_body(self):
        self.setup_feature_is_enabled()

    def test_if_rasp_event_collect_request_body(self):
        self.assert_feature_is_enabled(self.check_r)

    def setup_request_body_truncated(self):
        self.r = weblog.post("/rasp/ssrf", data={"domain": "169.254.169.254", "additional_data": "A" * 5000})

    @bug(library="java", weblog_variant="vertx3", reason="APPSEC-57811")
    def test_request_body_truncated(self):
        assert self.r.status_code == 403

        expected_http_value = "http://169.254.169.254"
        if context.library == "nodejs":
            expected_http_value += "/"

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {
                    "address": "server.io.net.url",
                    "value": expected_http_value,
                },
                "params": {
                    "address": "server.request.body",
                    "value": "169.254.169.254",
                },
            },
        )
        span = interfaces.library.get_root_span(request=self.r)
        meta_struct = span.get("meta_struct", {})
        body = meta_struct.get("http.request.body")
        assert body is not None
        print(body)
        assert body.get("domain") == "169.254.169.254"
        assert body.get("additional_data") == "A" * 4096
        meta = span.get("meta", {})
        assert meta.get("_dd.appsec.rasp.request_body_size.exceeded") == "true"

    def setup_if_no_rasp_event_no_collect_request_body(self):
        self.setup_feature_is_enabled()
        self.r = weblog.get(
            "/headers",
            headers={
                "User-Agent": "Arachni/v1",  # triggers appsec event
            },
        )

    def test_if_no_rasp_event_no_collect_request_body(self):
        self.assert_feature_is_enabled(self.check_r)
        assert self.r.status_code == 200
        span = interfaces.library.get_root_span(request=self.r)
        meta_struct = span.get("meta_struct", {})
        assert meta_struct.get("http.request.body") is None

    # TODO: implement test to check if request body size limit constrains
