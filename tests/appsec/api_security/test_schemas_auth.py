# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""API Security - authentication token schema extraction.

Covers the `extract-auth` post-processor (appsec-event-rules#289) which produces:
  - `_dd.appsec.s.req.jwt`     from `server.request.jwt`
  - `_dd.appsec.s.req.cookies` from `server.request.cookies`

Test cases mirror Emile Spir's checklist on APPSEC-68400:
  * request has JWT, no cookie          -> jwt schema generated
  * request has both JWT and cookie     -> both schemas generated
  * sensitive value in JWT/cookie       -> value never reported in the schema
  * JWT with a complex nested structure -> schema generated for nested fields

The "cookie, no JWT" case is omitted on purpose: request cookie schema extraction is produced by the
baseline extract-content processor (covered by Test_Schema_Request_Cookies), not by this PR.
"""

import base64
import json

from utils import interfaces, rfc, scenarios, weblog, features
from utils._weblog import HttpResponse


RFC_LINK = "https://docs.google.com/document/d/1OCHPBCAErOL2FhLl64YAHB8woDyq66y5t-JGolxdf1Q/edit#heading=h.bth088vsbjrz"


def get_schema(request: HttpResponse, address: str):
    """Get api security schema from spans"""
    span = interfaces.library.get_root_span(request)
    meta = span.get("meta", {})
    return meta.get("_dd.appsec.s." + address)


def get_meta_blob(request: HttpResponse) -> str:
    """Return the whole root-span meta serialized, to check a value never leaks anywhere."""
    span = interfaces.library.get_root_span(request)
    return json.dumps(span.get("meta", {}))


def _b64url(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def make_jwt(payload: dict, header: dict | None = None) -> str:
    """Build an unsigned-but-well-formed JWT (header.payload.signature)."""
    header = header or {"alg": "HS256", "typ": "JWT"}
    return f"{_b64url(header)}.{_b64url(payload)}.{base64.urlsafe_b64encode(b'signature').rstrip(b'=').decode()}"


# API Security schema type codes (see extract_schema generator)
STR = 8
INT = 4
BOOL = 2


def jwt_payload(schema: object) -> dict:
    """Extract the decoded JWT claims (payload) from a `_dd.appsec.s.req.jwt` schema.

    The JWT schema is split into header / payload / signature:
        [{"header": [{...}], "payload": [{...claims...}], "signature": [{"available": [2]}]}]
    """
    assert isinstance(schema, list), f"jwt schema should be a list, got {schema}"
    root = schema[0]
    assert set(root) >= {"header", "payload", "signature"}, f"unexpected jwt schema shape: {root}"
    return root["payload"][0]


SIMPLE_JWT = make_jwt({"sub": "1234567890", "name": "John Doe", "iat": 1516239022})
COMPLEX_JWT = make_jwt(
    {
        "sub": "1234567890",
        "user": {"id": 42, "roles": ["admin", "user"], "profile": {"team": "appsec"}},
        "scopes": ["read", "write"],
        "iat": 1516239022,
    }
)


# NB: a "cookie, no JWT" case is intentionally not tested here: request cookie schema extraction
# (_dd.appsec.s.req.cookies) is produced by the baseline extract-content processor and is already
# covered by Test_Schema_Request_Cookies. It does not exercise the new extract-auth processor, so such
# a test would pass even without the new rules. The res.cookies typo guard lives in
# Test_Schema_Request_Jwt_And_Cookie instead, which is genuinely gated on the new feature.


@rfc(RFC_LINK)
@scenarios.appsec_api_security
@features.auth_schemas
class Test_Schema_Request_Jwt_No_Cookie:
    """request has JWT, no cookie -> jwt schema generated"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS001/200", headers={"authorization": f"Bearer {SIMPLE_JWT}"})

    def test_request_method(self):
        assert self.request.status_code == 200
        jwt = get_schema(self.request, "req.jwt")
        root = jwt[0]
        # claims are decoded under "payload", with their scalar types
        payload = jwt_payload(jwt)
        assert payload["sub"] == [STR], payload
        assert payload["name"] == [STR], payload
        assert payload["iat"] == [INT], payload
        # header is decoded too
        assert root["header"][0] == {"alg": [STR], "typ": [STR]}, root["header"]
        # the signature is only reported as a presence boolean, never its value
        assert root["signature"][0] == {"available": [BOOL]}, root["signature"]


@rfc(RFC_LINK)
@scenarios.appsec_api_security
@features.auth_schemas
class Test_Schema_Request_Jwt_And_Cookie:
    """request has both JWT and cookie -> both schemas generated"""

    def setup_request_method(self):
        self.request = weblog.get(
            "/tag_value/api_match_AS001/200",
            headers={"authorization": f"Bearer {SIMPLE_JWT}"},
            cookies={"session": "any_value"},
        )

    def test_request_method(self):
        assert self.request.status_code == 200
        jwt = get_schema(self.request, "req.jwt")
        cookies = get_schema(self.request, "req.cookies")
        assert isinstance(cookies, list), f"_dd.appsec.s.req.cookies should be a list, got {cookies}"
        assert cookies[0] == {"session": [STR]}, cookies
        assert jwt_payload(jwt)["sub"] == [STR]
        # request cookies must land in req.cookies, not res.cookies (appsec-event-rules#289 typo guard)
        assert get_schema(self.request, "res.cookies") is None, "request cookies leaked into res.cookies (rules typo)"


@rfc(RFC_LINK)
@scenarios.appsec_api_security
@features.auth_schemas
class Test_Schema_Request_Auth_Sensitive_Value:
    """sensitive value in JWT/cookie -> only the structure is reported, never the value itself"""

    # values that must never appear in the schema (or anywhere in span meta)
    CARD = "5123456789123456"
    SSN = "123-45-6789"

    def setup_request_method(self):
        jwt = make_jwt({"sub": "1234567890", "ssn": self.SSN})
        self.request = weblog.get(
            "/tag_value/api_match_AS001/200",
            headers={"authorization": f"Bearer {jwt}"},
            cookies={"mastercard": self.CARD},
        )

    def test_request_method(self):
        assert self.request.status_code == 200
        cookies = get_schema(self.request, "req.cookies")
        # the SSN claim inside the JWT is reported as its type + PII classification, never the value:
        # scanners run on the decoded JWT content.
        assert jwt_payload(get_schema(self.request, "req.jwt"))["ssn"] == [STR, {"type": "us_ssn", "category": "pii"}]
        # the card number cookie keeps its key and string type, but not the value
        assert cookies[0]["mastercard"] == [STR], cookies
        # and the raw sensitive values must not leak anywhere in the span meta
        blob = get_meta_blob(self.request)
        assert self.CARD not in blob, "credit card value leaked into span meta"
        assert self.SSN not in blob, "SSN value leaked into span meta"


@rfc(RFC_LINK)
@scenarios.appsec_api_security
@features.auth_schemas
class Test_Schema_Request_Jwt_Complex:
    """JWT with a complex nested structure (maps with children, arrays) -> schema generated"""

    def setup_request_method(self):
        self.request = weblog.get("/tag_value/api_match_AS001/200", headers={"authorization": f"Bearer {COMPLEX_JWT}"})

    def test_request_method(self):
        assert self.request.status_code == 200
        payload = jwt_payload(get_schema(self.request, "req.jwt"))
        # array claim: element type + length metadata
        assert payload["scopes"] == [[[STR]], {"len": 2}], payload
        # nested object (map with children), including a child array and a deeper map
        user = payload["user"][0]
        assert user["id"] == [INT], user
        assert user["roles"] == [[[STR]], {"len": 2}], user
        assert user["profile"][0] == {"team": [STR]}, user
