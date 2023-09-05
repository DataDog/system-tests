# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, interfaces, released, rfc, scenarios, weblog


def get_schema(request, address):
    """get api security schema from spans"""
    for _, _, span in interfaces.library.get_spans(request):
        meta = span.get("meta", {})
        payload = meta.get("_dd.appsec.s." + address)
        if payload is not None:
            return payload
    return


def equal_without_meta(t1, t2):
    """compare two schema types, ignoring any metadata"""
    if t1 is None or t2 is None:
        print("NONE")
        return False
    return equal_value(t1[0], t2[0])


def equal_value(t1, t2):
    """compare two schema type values, ignoring any metadata"""
    if isinstance(t1, list) and isinstance(t2, list):
        return len(t1) == len(t2) and all(equal_without_meta(a, b) for a, b in zip(t1, t2))
    if isinstance(t1, dict) and isinstance(t2, dict):
        return len(t1) == len(t2) and all(equal_without_meta(t1[k], t2.get(k)) for k in t1)
    if isinstance(t1, int) and isinstance(t2, int):
        return t1 == t2
    return False


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@released(
    dotnet="?", java="?", php_appsec="?", python={"django-poc": "1.18", "flask-poc": "1.18", "*": "?"}, ruby="?",
)
@coverage.basic
@scenarios.appsec_api_security
class Test_Schema_Request_Headers:
    """Test API Security - Request Header Schema"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS001/200")

    def test_request_method(self):
        """can provide request header schema"""
        schema = get_schema(self.request, "req.headers")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        assert equal_without_meta(schema, [{"Accept-Encoding": [8], "Host": [8], "User-Agent": [8]}])


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@released(
    dotnet="?", java="?", php_appsec="?", python={"django-poc": "1.18", "flask-poc": "1.18", "*": "?"}, ruby="?",
)
@coverage.basic
@scenarios.appsec_api_security
class Test_Schema_Request_Query_Parameters:
    """Test API Security - Request Query Parameters Schema"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS002/200?x=123&y=abc&z=%7B%22key%22%3A%22value%22%7D")

    def test_request_method(self):
        """can provide request query parameters schema"""
        schema = get_schema(self.request, "req.query")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        for parameter_name in ("x", "y", "z"):
            assert parameter_name in schema[0]
            assert isinstance(schema[0][parameter_name], list)


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@released(
    dotnet="?", java="?", php_appsec="?", python={"django-poc": "1.18", "flask-poc": "1.18", "*": "?"}, ruby="?",
)
@coverage.basic
@scenarios.appsec_api_security
class Test_Schema_Request_Path_Parameters:
    """Test API Security - Request Path Parameters Schema"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS003/200")

    def test_request_method(self):
        """can provide request path parameters schema"""
        schema = get_schema(self.request, "req.params")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        # There should have two parameters here, one for api_match_AS003, the other for 200
        assert len(schema[0]) == 2
        assert all(isinstance(v, list) for v in schema[0].values())
        assert all(1 <= len(v) <= 2 for v in schema[0].values())
        assert all(isinstance(v[0], int) for v in schema[0].values())


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@released(
    dotnet="?", java="?", php_appsec="?", python={"django-poc": "1.18", "flask-poc": "1.18", "*": "?"}, ruby="?",
)
@coverage.basic
@scenarios.appsec_api_security
class Test_Schema_Request_Body:
    """Test API Security - Request Body and list length"""

    def setup_request_method(self):
        payload = {"main": [{"key": "id001", "value": 1345}, {"value": 1567, "key": "id002"}], "nullable": None}
        self.request = weblog.post("/tag_value/api_match_AS004/200", json=payload)

    def test_request_method(self):
        """can provide request request body schema"""
        schema = get_schema(self.request, "req.body")
        assert self.request.status_code == 200
        assert equal_without_meta(schema, [{"main": [[[{"key": [8], "value": [4]}]], {"len": 2}], "nullable": [1]}])


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@released(
    dotnet="?", java="?", php_appsec="?", python={"django-poc": "1.18", "flask-poc": "1.18", "*": "?"}, ruby="?",
)
@coverage.basic
@scenarios.appsec_api_security
class Test_Schema_Reponse_Headers:
    """Test API Security - Reponse Header Schema"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS005/200?X-option=test_value")

    def test_request_method(self):
        """can provide response header schema"""
        schema = get_schema(self.request, "res.headers")
        assert self.request.status_code == 200
        assert isinstance(schema, list)
        assert len(schema) == 1
        assert isinstance(schema[0], dict)
        for key in ("Content-Length", "Content-Type", "X-option"):
            assert key in schema[0]


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@released(dotnet="?", java="?", php_appsec="?", python="?", ruby="?")
@coverage.not_implemented
@scenarios.appsec_api_security
class Test_Schema_Reponse_Body:
    """Test API Security - Reponse Body Schema"""

    def setup_request_method(self):
        pass

    def test_request_method(self):
        """can provide response body schema"""
        pass
