from utils import features, weblog, interfaces, scenarios, rfc
from . import validate_rasp_attack


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_UrlQuery:
    def setup_sqli_get(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_get(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-942-100",
                {
                    "resource": {"address": "server.db.statement", "value": "SELECT * FROM table WHERE ? OR ? = ? --;"},
                    "params": {"address": "server.request.query", "value": "' OR 1 = 1 --"},
                    "db_type": {"address": "server.db.system"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyUrlEncoded:
    def setup_sqli_post_urlencoded(self):
        self.r = weblog.post("/rasp/sqli", data={"user_id": "' OR 1 = 1 --"})

    def test_sqli_post_urlencoded(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-942-100",
                {
                    "resource": {"address": "server.db.statement", "value": "SELECT * FROM table WHERE ? OR ? = ? --;"},
                    "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                    "db_type": {"address": "server.db.system"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyXml:
    def setup_sqli_post_xml(self):
        data = f"<?xml version='1.0' encoding='utf-8'?><user_id>' OR 1 = 1 --</user_id>"
        self.r = weblog.post("/rasp/sqli", data=data, headers={"Content-Type": "application/xml"})

    def test_sqli_post_xml(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-942-100",
                {
                    "resource": {"address": "server.db.statement", "value": "SELECT * FROM table WHERE ? OR ? = ? --;"},
                    "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                    "db_type": {"address": "server.db.system"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_sql_injection
@scenarios.appsec_rasp
class Test_Sqli_BodyJson:
    def setup_sqli_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/sqli", json={"user_id": "' OR 1 = 1 --"})

    def test_sqli_post_json(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-942-100",
                {
                    "resource": {"address": "server.db.statement", "value": "SELECT * FROM table WHERE ? OR ? = ? --;"},
                    "params": {"address": "server.request.body", "value": "' OR 1 = 1 --"},
                    "db_type": {"address": "server.db.system"},
                },
            )

        return True
