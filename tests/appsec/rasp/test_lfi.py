from utils import features, weblog, interfaces, scenarios, rfc
from . import validate_rasp_attack

@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_UrlQuery:
    def setup_lfi_get(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_get(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-930-100",
                {
                    "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                    "params": {"address": "server.request.query", "value": "../etc/passwd"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyUrlEncoded:
    def setup_lfi_post_urlencoded(self):
        self.r = weblog.post("/rasp/lfi", data={"file": "../etc/passwd"})

    def test_lfi_post_urlencoded(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-930-100",
                {
                    "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                    "params": {"address": "server.request.query", "value": "../etc/passwd"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyXml:
    def setup_lfi_post_xml(self):
        data = f"<?xml version='1.0' encoding='utf-8'?><file>../etc/passwd</file>"
        self.r = weblog.post("/rasp/lfi", data=data, headers={"Content-Type": "application/xml"})

    def test_lfi_post_xml(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-930-100",
                {
                    "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                    "params": {"address": "server.request.query", "value": "../etc/passwd"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_Lfi_BodyJson:
    def setup_lfi_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/lfi", json={"file": "../etc/passwd"})

    def test_lfi_post_json(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-930-100",
                {
                    "resource": {"address": "server.io.fs.file", "value": "../etc/passwd"},
                    "params": {"address": "server.request.query", "value": "../etc/passwd"},
                },
            )

        return True
