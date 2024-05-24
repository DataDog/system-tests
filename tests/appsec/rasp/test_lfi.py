# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_UrlQuery:
    """ Local file inclusion through query parameters """

    def setup_lfi_get(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_get(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.query", "value": "../etc/passwd"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyUrlEncoded:
    """ Local file inclusion through a url-encoded body parameter """

    def setup_lfi_post_urlencoded(self):
        self.r = weblog.post("/rasp/lfi", data={"file": "../etc/passwd"})

    def test_lfi_post_urlencoded(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.body", "value": "../etc/passwd"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyXml:
    """ Local file inclusion through an xml body parameter """

    def setup_lfi_post_xml(self):
        data = "<?xml version='1.0' encoding='utf-8'?><file>../etc/passwd</file>"
        self.r = weblog.post("/rasp/lfi", data=data, headers={"Content-Type": "application/xml"})

    def test_lfi_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.body", "value": "../etc/passwd"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.3nydvvu7sn93")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyJson:
    """ Local file inclusion through a json body parameter """

    def setup_lfi_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/lfi", json={"file": "../etc/passwd"})

    def test_lfi_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-930-100",
            {
                "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                "params": {"address": "server.request.body", "value": "../etc/passwd"},
            },
        )
