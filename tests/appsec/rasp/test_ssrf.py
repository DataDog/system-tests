from utils import features, weblog, interfaces, scenarios, rfc


def validate_rasp_attack(span, rule, parameters=None):
    assert "_dd.appsec.json" in span["meta"], "_dd.appsec.json not in meta"

    triggers = span["meta"]["_dd.appsec.json"]["triggers"]
    assert len(triggers) == 1, "multiple appsec events found, only one expected"

    trigger = triggers[0]
    obtained_rule_id = trigger["rule"]["id"]
    assert trigger["rule"]["id"] == rule, f"incorrect rule id, expected {rule}"

    if parameters is not None:
        rule_matches = trigger["rule_matches"]
        assert len(rule_matches) == 1, "multiple rule matches found, only one expected"

        rule_match_params = rule_matches[0]["parameters"]
        assert len(rule_match_params) == 1, "multiple parameters found, only one expected"

        obtained_parameters = rule_match_params[0]
        for name, fields in parameters.items():
            address = fields["address"]
            value = None
            if value in fields:
                value = fields["value"]

            assert name in obtained_parameters, f"parameter '{name}' not in rule match"

            obtained_param = obtained_parameters[name]

            assert obtained_param["address"] == address, f"incorrect address for '{name}', expected '{address}'"

            if value is not None:
                assert obtained_param["value"] == value, f"incorrect value for '{name}', expected '{value}'"


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Ssrf_UrlQuery:
    def setup_ssrf_get(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_get(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-934-100",
                {
                    "resource": {"address": "server.io.net.url", "value": "169.254.169.254"},
                    "params": {"address": "server.request.query", "value": "169.254.169.254"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Ssrf_BodyUrlEncoded:
    def setup_ssrf_post_urlencoded(self):
        self.r = weblog.post("/rasp/ssrf", data={"domain": "169.254.169.254"})

    def test_ssrf_post_urlencoded(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-934-100",
                {
                    "resource": {"address": "server.io.net.url", "value": "169.254.169.254"},
                    "params": {"address": "server.request.query", "value": "169.254.169.254"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Ssrf_BodyXml:
    def setup_ssrf_post_xml(self):
        data = f"<?xml version='1.0' encoding='utf-8'?><domain>169.254.169.254</domain>"
        self.r = weblog.post("/rasp/ssrf", data=data, headers={"Content-Type": "application/xml"})

    def test_ssrf_post_xml(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-934-100",
                {
                    "resource": {"address": "server.io.net.url", "value": "169.254.169.254"},
                    "params": {"address": "server.request.query", "value": "169.254.169.254"},
                },
            )

        return True


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Ssrf_BodyJson:
    def setup_ssrf_post_json(self):
        """AppSec detects attacks in JSON body values"""
        self.r = weblog.post("/rasp/ssrf", json={"domain": "169.254.169.254"})

    def test_ssrf_post_json(self):
        assert self.r.status_code == 403

        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_rasp_attack(
                span,
                "rasp-934-100",
                {
                    "resource": {"address": "server.io.net.url", "value": "169.254.169.254"},
                    "params": {"address": "server.request.query", "value": "169.254.169.254"},
                },
            )

        return True
