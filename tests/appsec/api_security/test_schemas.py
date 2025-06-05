# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, interfaces, missing_feature, rfc, scenarios, weblog, features, logger


def get_schema(request, address):
    """Get api security schema from spans"""
    span = interfaces.library.get_root_span(request)
    meta = span.get("meta", {})
    key = "_dd.appsec.s." + address
    if key not in meta:
        logger.info(f"Schema not found in span meta for {key}")
    return meta.get(key)


# can be used to match any value in a schema
ANY = ...


def contains(t1, t2):
    """Validate that schema t1 contains all keys and values from t2"""
    if t2 is ANY:
        return True
    if t1 is None or t2 is None:
        return False
    return equal_value(t1[0], t2[0])


def equal_value(t1, t2):
    """Compare two schema type values, ignoring any metadata"""
    if t2 is ANY:
        return True
    if isinstance(t1, list) and isinstance(t2, list):
        return len(t1) == len(t2) and all(contains(a, b) for a, b in zip(t1, t2, strict=False))
    if isinstance(t1, dict) and isinstance(t2, dict):
        return all(k in t1 and contains(t1[k], t2[k]) for k in t2)
    if isinstance(t1, int) and isinstance(t2, int):
        return t1 == t2
    return False


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Schema_Request_Headers:
    """Test API Security - Request Headers Schema"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS001/200")

    def test_request_method(self):
        """Can provide request header schema"""
        schema = get_schema(self.request, "req.headers")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        for parameter_name in ("accept-encoding", "host", "user-agent"):
            assert parameter_name in schema[0]
            assert isinstance(schema[0][parameter_name], list)


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Schema_Request_Cookies:
    """Test API Security - Request Cookies Schema"""

    def setup_request_method(self):
        self.request = weblog.get(
            "/tag_value/api_match_AS001/200", cookies={"secret": "any_value", "cache": "any_other_value"}
        )

    @missing_feature(context.library < "python@1.19.0.dev")
    def test_request_method(self):
        """Can provide request header schema"""
        schema = get_schema(self.request, "req.cookies")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        for parameter_name in ("secret", "cache"):
            assert parameter_name in schema[0]
            assert isinstance(schema[0][parameter_name], list)


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Schema_Request_Query_Parameters:
    """Test API Security - Request Query Parameters Schema"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS002/200?x=123&y=abc&z=%7B%22key%22%3A%22value%22%7D")

    def test_request_method(self):
        """Can provide request query parameters schema"""
        schema = get_schema(self.request, "req.query")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)
        for parameter_name in ("x", "y", "z"):
            assert parameter_name in schema[0]
            assert isinstance(schema[0][parameter_name], list)


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Schema_Request_Path_Parameters:
    """Test API Security - Request Path Parameters Schema"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS003/200")

    def test_request_method(self):
        """Can provide request path parameters schema"""
        schema = get_schema(self.request, "req.params")
        assert self.request.status_code == 200
        assert schema
        assert isinstance(schema, list)

        for route_parameter in ("tag_value", "status_code"):
            parameter = schema[0][route_parameter]
            assert isinstance(parameter[0], int)


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Schema_Request_Json_Body:
    """Test API Security - Request Body and list length"""

    def setup_request_method(self):
        payload = {
            "main": [{"key": "id001", "value": 1345.67}, {"value": 1567.89, "key": "id002"}],
            "nullable": None,
        }
        self.request = weblog.post("/tag_value/api_match_AS004/200", json=payload)

    def test_request_method(self):
        """Can provide request request body schema"""
        schema = get_schema(self.request, "req.body")
        assert self.request.status_code == 200
        assert contains(schema, [{"main": [[[{"key": [8], "value": [16]}]], {"len": 2}], "nullable": [1]}])


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Schema_Request_FormUrlEncoded_Body:
    """Test API Security - Request Body and list length"""

    def setup_request_method(self):
        self.request = weblog.post(
            "/tag_value/api_match_AS004/200",
            data={
                "main[0][key]": "id001",
                "main[0][value]": 1345,
                "main[1][key]": "id002",
                "main[1][value]": 1567,
                "nullable": "",
            },
        )

    def test_request_method(self):
        """Can provide request request body schema"""
        schema = get_schema(self.request, "req.body")
        assert self.request.status_code == 200
        assert (
            contains(schema, [{"main": [[[{"key": [8], "value": [8]}]], {"len": 2}], "nullable": [8]}])
            or contains(schema, [{"main": [[[{"key": [8], "value": [16]}]], {"len": 2}], "nullable": [1]}])
            or contains(
                schema,
                [
                    {
                        "main[0][key]": ANY,
                        "main[0][value]": ANY,
                        "main[1][key]": ANY,
                        "main[1][value]": ANY,
                        # "nullable": ANY,  # some frameworks may drop that value
                    }
                ],
            )
        ), schema


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Schema_Response_Headers:
    """Test API Security - Response Header Schema"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS005/200?X-option=test_value")

    def test_request_method(self):
        """Can provide response header schema"""
        schema = get_schema(self.request, "res.headers")
        assert self.request.status_code == 200
        assert isinstance(schema, list)
        assert len(schema) == 1
        assert isinstance(schema[0], dict)
        assert "x-option" in schema[0]


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Schema_Response_Body:
    """Test API Security - Response Body Schema with urlencoded body"""

    def setup_request_method(self):
        self.request = weblog.post(
            "/tag_value/payload_in_response_body_001/200",
            data={"test_int": 1, "test_str": "anything", "test_bool": True, "test_float": 1.5234},
        )

    def test_request_method(self):
        """Can provide response body schema"""
        assert self.request.status_code == 200

        schema = get_schema(self.request, "res.body")
        assert isinstance(schema, list), f"_dd.appsec.s.res.body meta tag should be a list, got {schema}"
        assert len(schema) == 1, f"{schema} is not a list of length 1"
        for key in ("payload",):
            assert key in schema[0]
        payload_schema = schema[0]["payload"][0]
        for key in ("test_bool", "test_int", "test_str", "test_float"):
            assert key in payload_schema


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security_no_response_body
@features.api_security_schemas
class Test_Schema_Response_Body_env_var:
    """Test API Security - Response Body Schema with urlencoded body and env var disabling response body parsing
    Check that response headers are still parsed but not response body
    """

    def setup_request_method(self):
        self.request = weblog.post(
            "/tag_value/payload_in_response_body_001/200?X-option=test_value",
            data={"test_int": 1, "test_str": "anything", "test_bool": True, "test_float": 1.5234},
        )

    def test_request_method(self):
        """Can provide response body schema"""
        assert self.request.status_code == 200

        headers_schema = get_schema(self.request, "res.headers")
        assert isinstance(headers_schema, list)
        assert len(headers_schema) == 1
        assert isinstance(headers_schema[0], dict)
        assert "x-option" in headers_schema[0]

        body_schema = get_schema(self.request, "res.body")
        assert body_schema is None


@rfc("https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz")
@scenarios.appsec_api_security
@features.api_security_schemas
class Test_Scanners:
    """Test API Security - Scanners"""

    def setup_request_method(self):
        self.request = weblog.get(
            "/tag_value/api_match_AS001/200",
            cookies={"mastercard": "5123456789123456", "authorization": "digest_a0b1c2", "SSN": "123-45-6789"},
            headers={"authorization": "digest a0b1c2"},
        )

    @missing_feature(context.library < "python@1.19.0.dev")
    def test_request_method(self):
        """Can provide request header schema"""
        schema_cookies = get_schema(self.request, "req.cookies")
        schema_headers = get_schema(self.request, "req.headers")
        assert self.request.status_code == 200
        assert schema_cookies
        assert isinstance(schema_cookies, list)
        # some tracers report headers / cookies values as lists even if there's just one element (frameworks do)
        # in this case, the second case of expected variables below would pass
        expected_cookies: list[dict] = [
            {
                "SSN": [8, {"category": "pii", "type": "us_ssn"}],
                "authorization": [8],
                "mastercard": [8, {"card_type": "mastercard", "type": "card", "category": "payment"}],
            },
            {
                "SSN": [[[8, {"category": "pii", "type": "us_ssn"}]], {"len": 1}],
                "authorization": [[[8]], {"len": 1}],
                "mastercard": [[[8, {"card_type": "mastercard", "type": "card", "category": "payment"}]], {"len": 1}],
            },
        ]
        expected_headers: list[dict] = [
            {"authorization": [8, {"category": "credentials", "type": "digest_auth"}]},
            {"authorization": [[[8, {"category": "credentials", "type": "digest_auth"}]], {"len": 1}]},
        ]

        for schema, expected in [
            (schema_cookies[0], expected_cookies),
            (schema_headers[0], expected_headers),
        ]:
            for key in expected[0]:
                assert key in schema
                assert isinstance(schema[key], list)
                assert len(schema[key]) == len(expected[0][key]) or len(schema[key]) == len(expected[1][key])
                if len(schema[key]) == 2:
                    assert schema[key][1] == expected[1][key][1] or schema[key][1] == expected[0][key][1]
