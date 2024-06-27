# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc, context


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3r1lwuv4y2g3")
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Ssrf_UrlQuery:
    """ Server-side request forgery through query parameters """

    def setup_ssrf_get(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_get(self):
        assert self.r.status_code == 403

        expected_http_value = "http://169.254.169.254"
        if context.library == "nodejs":
            expected_http_value += "/"

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {"address": "server.io.net.url", "value": expected_http_value},
                "params": {"address": "server.request.query", "value": "169.254.169.254"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3r1lwuv4y2g3")
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Ssrf_BodyUrlEncoded:
    """ Server-side request forgery through a url-encoded body parameter """

    def setup_ssrf_post_urlencoded(self):
        self.r = weblog.post("/rasp/ssrf", data={"domain": "169.254.169.254"})

    def test_ssrf_post_urlencoded(self):
        assert self.r.status_code == 403

        expected_http_value = "http://169.254.169.254"
        if context.library == "nodejs":
            expected_http_value += "/"

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {"address": "server.io.net.url", "value": expected_http_value},
                "params": {"address": "server.request.body", "value": "169.254.169.254"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3r1lwuv4y2g3")
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Ssrf_BodyXml:
    """ Server-side request forgery through an xml body parameter """

    def setup_ssrf_post_xml(self):
        data = f"<?xml version='1.0' encoding='utf-8'?><domain>169.254.169.254</domain>"
        self.r = weblog.post("/rasp/ssrf", data=data, headers={"Content-Type": "application/xml"})

    def test_ssrf_post_xml(self):
        assert self.r.status_code == 403

        expected_http_value = "http://169.254.169.254"
        if context.library == "nodejs":
            expected_http_value += "/"

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {"address": "server.io.net.url", "value": expected_http_value},
                "params": {"address": "server.request.body", "value": "169.254.169.254"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3r1lwuv4y2g3")
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Ssrf_BodyJson:
    """ Server-side request forgery through a json body parameter """

    def setup_ssrf_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/ssrf", json={"domain": "169.254.169.254"})

    def test_ssrf_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-934-100",
            {
                "resource": {"address": "server.io.net.url", "value": "http://169.254.169.254/"},
                "params": {"address": "server.request.body", "value": "169.254.169.254"},
            },
        )
