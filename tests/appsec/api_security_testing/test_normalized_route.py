# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

import re

from utils import interfaces, rfc, weblog, features, scenarios
from utils._weblog import HttpResponse


NORMALIZED_ROUTE_TAG = "_dd.appsec.normalized_route"
HTTP_ROUTE_TAG = "http.route"

# RFC-1103 syntax validator for `_dd.appsec.normalized_route`.
# Atomic elements are slash-separated; static constants use [A-Za-z0-9.-~_] or
# percent-encoded sequences; dynamic parameters use {name} where name may
# contain anything except the six reserved characters /?#+{} (with `+` allowed
# only as the rule-5 combining marker between framework-supplied subnames).
# Percent-encoded sequences are accepted in either case (RFC 3986 normalization
# treats them as equivalent), even though the RFC text recommends uppercase.
_STATIC_CHAR = r"[A-Za-z0-9.\-~_]|%[0-9A-Fa-f]{2}"
_PARAM_NAME = r"(?:[^/?#+{}]|%[0-9A-Fa-f]{2})+(?:\+(?:[^/?#+{}]|%[0-9A-Fa-f]{2})+)*"
_ATOMIC_ELEMENT = rf"(?:(?:{_STATIC_CHAR})+|\{{{_PARAM_NAME}\}})"
_NORMALIZED_ROUTE_REGEX = re.compile(rf"^/(?:{_ATOMIC_ELEMENT}(?:/{_ATOMIC_ELEMENT})*/?)?$")


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
    assert normalized is not None, (
        f"{NORMALIZED_ROUTE_TAG} must be set when {HTTP_ROUTE_TAG}={meta[HTTP_ROUTE_TAG]!r} and API Security is enabled"
    )
    assert isinstance(normalized, str), f"{NORMALIZED_ROUTE_TAG} must be a string, got {type(normalized).__name__}"
    # Every emitted value must conform to the RFC grammar regardless of the
    # underlying route shape; a malformed value is a tracer bug.
    assert _NORMALIZED_ROUTE_REGEX.match(normalized), (
        f"{NORMALIZED_ROUTE_TAG}={normalized!r} does not conform to RFC-1103 syntax"
    )
    return normalized


@rfc("https://docs.google.com/document/d/1XfjniR6v6pL2V5JtxYdpiKbOF08tA9q2Sefk36gtXhs")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRoute:
    """RFC-1103: tracers emit `_dd.appsec.normalized_route` on every request
    span that already carries `http.route` when API Security is enabled.

    The tag is a per-request, framework-agnostic representation of the matched
    route. Rules 1-6 govern leading slash, atomic-element separation,
    static-constant character set, parameter-name grammar, intra-segment
    composition and the catch-all tail exception.
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
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteMultiParamsInSegment:
    """RFC-1103 rule 5: two mandatory path parameters within a single URL segment.

    When a route template places two dynamic parameters inside the same
    path segment (e.g. `/<id>-<format>`), the tracer must collapse them into a
    single atomic element using the `+` combining marker, in declaration order:
    `{id+format}`.  The resulting normalized route is deterministic and
    identical across all weblogs because the parameter names `id` and `format`
    are fixed in the endpoint declaration.
    """

    def setup_multi_params_in_segment(self):
        self.r = weblog.get("/api_security/multi-params-in-segment/123-json")

    def test_multi_params_in_segment(self):
        """Rule 5: two intra-segment params are joined with `+` into `{id+format}`."""
        meta = _get_meta(self.r)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/multi-params-in-segment/{id+format}", (
            f"expected '/api_security/multi-params-in-segment/{{id+format}}', got {normalized!r}"
        )


@rfc("https://docs.google.com/document/d/1XfjniR6v6pL2V5JtxYdpiKbOF08tA9q2Sefk36gtXhs")
@features.api_security_normalized_route
@scenarios.appsec_api_security
class Test_NormalizedRouteOptionalParams:
    """RFC-1103 rule 5 + optional-element resolution: an optional path parameter
    that shares a URL segment with a mandatory parameter must be combined with `+`
    when present (`{id+format}`) and dropped from the combined name when absent,
    leaving the mandatory parameter alone (`{id}`).

    The two requests target the same route declaration but resolve to distinct
    normalized routes, which is intentional per rule 6.
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
        self.r_with = weblog.get("/api_security/optional-params/123-json")

    def test_with_optional(self):
        """Optional param present in same segment: combined as `{id+format}`."""
        meta = _get_meta(self.r_with)
        normalized = _require_normalized(meta)
        assert normalized == "/api_security/optional-params/{id+format}", (
            f"expected '/api_security/optional-params/{{id+format}}', got {normalized!r}"
        )

    def setup_optional_routes_are_distinct(self):
        self.r_without = weblog.get("/api_security/optional-params/123")
        self.r_with = weblog.get("/api_security/optional-params/123-json")

    def test_optional_routes_are_distinct(self):
        """The two requests yield distinct normalized routes (rule 6)."""
        meta_without = _get_meta(self.r_without)
        meta_with = _get_meta(self.r_with)
        normalized_without = _require_normalized(meta_without)
        normalized_with = _require_normalized(meta_with)
        assert normalized_without != normalized_with, (
            f"optional-absent and optional-present routes must differ; both got {normalized_without!r}"
        )
