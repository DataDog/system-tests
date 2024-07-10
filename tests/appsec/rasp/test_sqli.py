# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.gv4kwto3561e")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_UrlQuery:
    """ SQL Injection through query parameters """

    def setup_sqli_get(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_get(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement", "value": "SELECT * FROM users WHERE id=? OR ? = ? --'"},
                "params": {"address": "server.request.query", "value": "' OR 1 = 1 --"},
                "db_type": {"address": "server.db.system"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.gv4kwto3561e")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyUrlEncoded:
    """ SQL Injection through a url-encoded body parameter """

    def setup_sqli_post_urlencoded(self):
        self.r = weblog.post("/rasp/sqli", data={"user_id": "' OR 1 = 1 --"})

    def test_sqli_post_urlencoded(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement", "value": "SELECT * FROM users WHERE id=? OR ? = ? --'"},
                "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                "db_type": {"address": "server.db.system"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.gv4kwto3561e")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyXml:
    """ SQL Injection through an xml body parameter """

    def setup_sqli_post_xml(self):
        data = "<?xml version='1.0' encoding='utf-8'?><user_id>' OR 1 = 1 --</user_id>"
        self.r = weblog.post("/rasp/sqli", data=data, headers={"Content-Type": "application/xml"})

    def test_sqli_post_xml(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement", "value": "SELECT * FROM users WHERE id=? OR ? = ? --'"},
                "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                "db_type": {"address": "server.db.system"},
            },
        )


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.gv4kwto3561e")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyJson:
    """ SQL Injection through a json body parameter """

    def setup_sqli_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/sqli", json={"user_id": "' OR 1 = 1 --"})

    def test_sqli_post_json(self):
        assert self.r.status_code == 403

        interfaces.library.assert_rasp_attack(
            self.r,
            "rasp-942-100",
            {
                "resource": {"address": "server.db.statement", "value": "SELECT * FROM users WHERE id=? OR ? = ? --'"},
                "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                "db_type": {"address": "server.db.system"},
            },
        )
