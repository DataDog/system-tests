# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

import re

from utils import interfaces, rfc, weblog, features, scenarios
from utils._weblog import HttpResponse


NORMALIZED_ROUTE_TAG = "_dd.appsec.normalized_route"
HTTP_ROUTE_TAG = "http.route"

# RFC-1125 grammar for `_dd.appsec.normalized_route` (it replaces the
# RFC-1103 normalization rules):
#   route   = "/" / 1*( "/" segment ) [ "/" ]
#   segment = 1*( literal / "{" name "}" )
#   name    = 1*( ALPHA / DIGIT / "_" )
# A literal is static text in which every character other than
# A-Z a-z 0-9 - . _ ~ is percent-encoded with uppercase hex. Static text and
# several parameters can share a segment (`user-{id}`, `{id}.{format}`).
_LITERAL_CHAR = r"[A-Za-z0-9.\-~_]|%[0-9A-F]{2}"
_PARAM = r"\{[A-Za-z0-9_]+\}"
_SEGMENT = rf"(?:{_LITERAL_CHAR}|{_PARAM})+"
_NORMALIZED_ROUTE_REGEX = re.compile(rf"^/(?:{_SEGMENT}(?:/{_SEGMENT})*/?)?$")


def _get_meta(response: HttpResponse) -> dict:
    assert response.status_code == 200, f"unexpected status {response.status_code}: {response!r}"
    span = interfaces.library.get_root_span(request=response)
    return span.get("meta", {}) or {}


def _require_normalized(meta: dict) -> str:
    # Per RFC, the tag is required whenever `http.route` is present and API
    # Security is enabled. Surface a clearer message than a None mismatch
    # when the framework does not (yet) set `http.route` at all.
    assert meta.get(HTTP_ROUTE_TAG), (
        f"{HTTP_ROUTE_TAG} not set on entry span; normalized_route contract is conditioned on it"
    )
    normalized = meta.get(NORMALIZED_ROUTE_TAG)
    assert normalized is not None, f"{NORMALIZED_ROUTE_TAG} must be set when {HTTP_ROUTE_TAG}={meta[HTTP_ROUTE_TAG]!r}"
    assert isinstance(normalized, str), f"{NORMALIZED_ROUTE_TAG} must be a string, got {type(normalized).__name__}"
    # Every emitted value must conform to the RFC grammar regardless of the
    # underlying route shape; a malformed value is a tracer bug.
    assert _NORMALIZED_ROUTE_REGEX.match(normalized), (
        f"{NORMALIZED_ROUTE_TAG}={normalized!r} does not conform to the RFC-1125 grammar"
    )
    return normalized


@rfc("https://docs.google.com/document/d/1XfjniR6v6pL2V5JtxYdpiKbOF08tA9q2Sefk36gtXhs")
@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRoute:
    """RFC-1103, amended by RFC-1125: tracers emit `_dd.appsec.normalized_route`
    on every request span that already carries `http.route` when API Security
    is enabled.

    The tag is a per-request, framework-agnostic representation of the matched
    route, as an OpenAPI path template that follows the RFC-1125 grammar.
    """

    def setup_static_route(self):
        self.r_static = weblog.get("/waf")

    def test_static_route(self):
        """A static route (no path parameters) normalizes to its literal path.

        `/waf` is declared without parameters across all weblogs, so the
        normalized route is fully determined by the declaration and must match
        exactly. This also exercises rule 1 (leading slash) and rule 3
        (safe-character static constant) without any framework-specific naming.
        """
        meta = _get_meta(self.r_static)
        normalized = _require_normalized(meta)
        assert normalized == "/waf", f"expected '/waf', got {normalized!r}"

    def setup_single_param_route_with_static_prefix(self):
        # `/sample_rate_route/0` resolves under a static-prefixed parameterized
        # route. The static prefix `sample_rate_route` lets us also assert
        # the underscore is preserved as part of rule 3's safe character set.
        self.r_single_param = weblog.get("/sample_rate_route/0")

    def test_single_param_route_with_static_prefix(self):
        """Rule 3 + rule 5: underscore stays unencoded in the static segment;
        the trailing segment is exactly one `{name}` (single-param-per-segment).
        """
        meta = _get_meta(self.r_single_param)
        normalized = _require_normalized(meta)
        # First atomic element is a static constant with an underscore; second
        # is a single dynamic parameter. Don't pin the param name -- it differs
        # across framework conventions.
        assert re.fullmatch(r"/sample_rate_route/\{[^/{}]+\}", normalized), (
            f"expected '/sample_rate_route/{{<param>}}', got {normalized!r}"
        )

    def setup_two_param_route(self):
        # `/tag_value/<tag>/<status>` is declared across every weblog with two
        # consecutive dynamic parameters in two separate URL segments. Rule 5
        # then requires one atomic element per segment.
        self.r_two_param = weblog.get("/tag_value/foo/200")

    def test_two_param_route(self):
        """Rule 5: two parameters in separate segments yield two atomic dynamic elements.

        The parameter names themselves are framework-supplied (the weblogs use
        `tag_value`/`status_code` in most stacks but `tag`/`status` in the
        .NET controller); the contract under test is the structural shape,
        not the exact names. The names must still conform to the RFC grammar,
        which the regex validator enforces.
        """
        meta = _get_meta(self.r_two_param)
        normalized = _require_normalized(meta)
        assert re.fullmatch(r"/tag_value/\{[^/{}]+\}/\{[^/{}]+\}", normalized), (
            f"expected '/tag_value/{{<param1>}}/{{<param2>}}', got {normalized!r}"
        )

    def setup_query_string_not_in_route(self):
        # Rule 5 reminder: query parameters must not appear in the normalized
        # route. The /headers endpoint accepts query parameters but they must
        # be stripped from the normalized form.
        self.r_with_qs = weblog.get("/headers?one=1&two=2")

    def test_query_string_not_in_route(self):
        """Rule 5 reminder: query parameters are not part of the normalized route."""
        meta = _get_meta(self.r_with_qs)
        normalized = _require_normalized(meta)
        assert "?" not in normalized, f"query string leaked into normalized route: {normalized!r}"
        # `/headers` is also declared without parameters across weblogs.
        assert normalized == "/headers", f"expected '/headers', got {normalized!r}"


@rfc("https://docs.google.com/document/d/1XfjniR6v6pL2V5JtxYdpiKbOF08tA9q2Sefk36gtXhs")
@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteMultiParamsInSegment:
    """RFC-1125: two mandatory path parameters within a single URL segment.

    When a route template places two dynamic parameters inside the same
    path segment (e.g. `/<id>.<format>`), each parameter is its own template
    expression and the static text between them is kept, as OpenAPI path
    templating requires: `{id}.{format}`. RFC-1103's `+` combining
    (`{id+format}`) is replaced.
    """

    def setup_multi_params_in_segment(self):
        self.r = weblog.get("/api_security/multi-params-in-segment/123.json")

    def test_multi_params_in_segment(self):
        """Two intra-segment params stay separate, with the `.` between them."""
        meta = _get_meta(self.r)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/multi-params-in-segment/{id}.{format}", (
            f"expected '/api_security/multi-params-in-segment/{{id}}.{{format}}', got {normalized!r}"
        )

    def setup_three_params_in_segment(self):
        self.r_three_params_in_segment = weblog.get("/api_security/three-params/1-2-3")

    def test_three_params_in_segment(self):
        """RFC-1125 test 13: three params in one segment, with the `-` between them."""
        meta = _get_meta(self.r_three_params_in_segment)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/three-params/{a}-{b}-{c}", (
            f"expected '/api_security/three-params/{{a}}-{{b}}-{{c}}', got {normalized!r}"
        )


@rfc("https://docs.google.com/document/d/1XfjniR6v6pL2V5JtxYdpiKbOF08tA9q2Sefk36gtXhs")
@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteOptionalParams:
    """RFC-1125 optional path parameters: an optional parameter that shares a
    URL segment with a mandatory parameter is included, with the static text
    before it, when present in the request (`{id}.{format}`) and left out when
    absent (`{id}`).

    The two requests target the same route declaration but resolve to distinct
    normalized routes: the tag describes the effective route of each request.
    """

    def setup_without_optional(self):
        self.r_without = weblog.get("/api_security/optional-params/123")

    def test_without_optional(self):
        """Optional param absent: normalized route contains only the mandatory `{id}`."""
        meta = _get_meta(self.r_without)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/optional-params/{id}", (
            f"expected '/api_security/optional-params/{{id}}', got {normalized!r}"
        )

    def setup_with_optional(self):
        self.r_with = weblog.get("/api_security/optional-params/123.json")

    def test_with_optional(self):
        """Optional param present in the same segment: kept separate, as `{id}.{format}`."""
        meta = _get_meta(self.r_with)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/optional-params/{id}.{format}", (
            f"expected '/api_security/optional-params/{{id}}.{{format}}', got {normalized!r}"
        )

    def setup_optional_routes_are_distinct(self):
        self.r_without = weblog.get("/api_security/optional-params/123")
        self.r_with = weblog.get("/api_security/optional-params/123.json")

    def test_optional_routes_are_distinct(self):
        """The two requests yield distinct normalized routes (per-request value)."""
        meta_without = _get_meta(self.r_without)
        meta_with = _get_meta(self.r_with)
        normalized_without = _require_normalized(meta_without)
        normalized_with = _require_normalized(meta_with)
        assert normalized_without != normalized_with, (
            f"optional-absent and optional-present routes must differ; both got {normalized_without!r}"
        )


@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteStaticTextInSegment:
    """RFC-1125 tests 6-8: static text in a segment is kept next to the parameter.

    `/api_security/static-text/user-{id}` is a valid OpenAPI path template as
    written, so it is not folded into `/api_security/static-text/{id}`.
    """

    def setup_static_text_in_segment(self):
        self.r = weblog.get("/api_security/static-text/user-42")

    def test_static_text_in_segment(self):
        """The static prefix `user-` stays in the segment of its parameter."""
        meta = _get_meta(self.r)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/static-text/user-{id}", (
            f"expected '/api_security/static-text/user-{{id}}', got {normalized!r}"
        )

    def setup_static_text_before_param(self):
        self.r_static_text_before_param = weblog.get("/api_security/version/v2/items")

    def test_static_text_before_param(self):
        """RFC-1125 test 7: static text before the parameter of a segment."""
        meta = _get_meta(self.r_static_text_before_param)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/version/v{version}/items", (
            f"expected '/api_security/version/v{{version}}/items', got {normalized!r}"
        )

    def setup_static_text_after_param(self):
        self.r_static_text_after_param = weblog.get("/api_security/files/report.json")

    def test_static_text_after_param(self):
        """RFC-1125 test 8: static text after the parameter of a segment."""
        meta = _get_meta(self.r_static_text_after_param)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/files/{name}.json", (
            f"expected '/api_security/files/{{name}}.json', got {normalized!r}"
        )


@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteOptionalSegment:
    """RFC-1125: an optional parameter in a segment of its own.

    The optional part is in the tag when the request has it and left out,
    with the `/` before it, when it does not. The tag is never omitted
    because of an optional parameter.
    """

    def setup_optional_segment_absent(self):
        self.r_absent = weblog.get("/api_security/optional-segment/1")

    def test_optional_segment_absent(self):
        """Absent optional: only the mandatory `{id}`."""
        meta = _get_meta(self.r_absent)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/optional-segment/{id}", (
            f"expected '/api_security/optional-segment/{{id}}', got {normalized!r}"
        )

    def setup_optional_segment_present(self):
        self.r_present = weblog.get("/api_security/optional-segment/1/posts")

    def test_optional_segment_present(self):
        """Present optional: `{id}/{tab}`."""
        meta = _get_meta(self.r_present)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/optional-segment/{id}/{tab}", (
            f"expected '/api_security/optional-segment/{{id}}/{{tab}}', got {normalized!r}"
        )


@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteCatchAll:
    """RFC-1125: a catch-all is a single parameter, even though its value
    spans several segments (the declared OpenAPI exception).

    The catch-all name is framework-specific: named catch-alls keep their
    name, and symbol-only ones (`*`) get `param<N>`.
    """

    def setup_catch_all(self):
        self.r = weblog.get("/api_security/catch-all/a/b/c.txt")

    def test_catch_all(self):
        """The whole remainder `a/b/c.txt` is one parameter, with no request value in the tag."""
        meta = _get_meta(self.r)
        normalized = _require_normalized(meta)
        assert re.fullmatch(rf"/api_security/catch-all/{_PARAM}", normalized), (
            f"expected '/api_security/catch-all/{{<param>}}', got {normalized!r}"
        )


@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteRoot:
    """RFC-1125 test 2: the root route normalizes to `/`."""

    def setup_root_route(self):
        self.r_root_route = weblog.get("/")

    def test_root_route(self):
        """The root route `/` is `/`; it is never an empty tag."""
        meta = _get_meta(self.r_root_route)
        normalized = _require_normalized(meta)
        assert normalized == "/", (
            f"expected '/', got {normalized!r}"
        )


@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteOptionalAfterStaticText:
    """RFC-1125 tests 19-20: an optional parameter after static text in the
    same segment (`/api_security/search.{format?}`). When absent, it is left
    out with the `.` before it.
    """

    def setup_optional_after_static_text_absent(self):
        self.r_optional_after_static_text_absent = weblog.get("/api_security/search")

    def test_optional_after_static_text_absent(self):
        """Test 19: absent, the `.` goes with it."""
        meta = _get_meta(self.r_optional_after_static_text_absent)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/search", (
            f"expected '/api_security/search', got {normalized!r}"
        )

    def setup_optional_after_static_text_present(self):
        self.r_optional_after_static_text_present = weblog.get("/api_security/search.json")

    def test_optional_after_static_text_present(self):
        """Test 20: present, `.{format}`."""
        meta = _get_meta(self.r_optional_after_static_text_present)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/search.{format}", (
            f"expected '/api_security/search.{{format}}', got {normalized!r}"
        )


@rfc("https://docs.google.com/document/d/1EFXGA1DI_tAjNWsWzSwjIqTxjxokXI0OeRKdlU_ZRdY")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteMultipleOptionals:
    """RFC-1125 tests 21-23: several optional parameters in a row
    (`/api_security/optional-chain/{x?}/{y?}`); each is in the tag only when
    the request has it.
    """

    def setup_multiple_optionals_none(self):
        self.r_multiple_optionals_none = weblog.get("/api_security/optional-chain")

    def test_multiple_optionals_none(self):
        """Test 21: no optional present."""
        meta = _get_meta(self.r_multiple_optionals_none)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/optional-chain", (
            f"expected '/api_security/optional-chain', got {normalized!r}"
        )

    def setup_multiple_optionals_first(self):
        self.r_multiple_optionals_first = weblog.get("/api_security/optional-chain/1")

    def test_multiple_optionals_first(self):
        """Test 22: the first optional present."""
        meta = _get_meta(self.r_multiple_optionals_first)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/optional-chain/{x}", (
            f"expected '/api_security/optional-chain/{{x}}', got {normalized!r}"
        )

    def setup_multiple_optionals_both(self):
        self.r_multiple_optionals_both = weblog.get("/api_security/optional-chain/1/2")

    def test_multiple_optionals_both(self):
        """Test 23: both optionals present."""
        meta = _get_meta(self.r_multiple_optionals_both)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/optional-chain/{x}/{y}", (
            f"expected '/api_security/optional-chain/{{x}}/{{y}}', got {normalized!r}"
        )
