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

    @staticmethod
    def _get_meta(response: HttpResponse) -> dict:
        assert response.status_code == 200, f"unexpected status {response.status_code}: {response!r}"
        span = interfaces.library.get_root_span(request=response)
        return span.get("meta", {}) or {}

    @staticmethod
    def _require_normalized(meta: dict) -> str:
        # Per RFC, the tag is required whenever `http.route` is present and API
        # Security is enabled. Surface a clearer message than a None mismatch
        # when the framework does not (yet) set `http.route` at all.
        assert meta.get(HTTP_ROUTE_TAG), (
            f"{HTTP_ROUTE_TAG} not set on entry span; normalized_route contract is conditioned on it"
        )
        normalized = meta.get(NORMALIZED_ROUTE_TAG)
        assert normalized is not None, (
            f"{NORMALIZED_ROUTE_TAG} must be set when {HTTP_ROUTE_TAG}={meta[HTTP_ROUTE_TAG]!r} "
            f"and API Security is enabled"
        )
        assert isinstance(normalized, str), f"{NORMALIZED_ROUTE_TAG} must be a string, got {type(normalized).__name__}"
        # Every emitted value must conform to the RFC grammar regardless of the
        # underlying route shape; a malformed value is a tracer bug.
        assert _NORMALIZED_ROUTE_REGEX.match(normalized), (
            f"{NORMALIZED_ROUTE_TAG}={normalized!r} does not conform to RFC-1103 syntax"
        )
        return normalized

    def setup_static_route(self):
        self.r_static = weblog.get("/waf")

    def test_static_route(self):
        """A static route (no path parameters) normalizes to its literal path.

        `/waf` is declared without parameters across all weblogs, so the
        normalized route is fully determined by the declaration and must match
        exactly. This also exercises rule 1 (leading slash) and rule 3
        (safe-character static constant) without any framework-specific naming.
        """
        meta = self._get_meta(self.r_static)
        normalized = self._require_normalized(meta)
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
        meta = self._get_meta(self.r_single_param)
        normalized = self._require_normalized(meta)
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
        meta = self._get_meta(self.r_two_param)
        normalized = self._require_normalized(meta)
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
        meta = self._get_meta(self.r_with_qs)
        normalized = self._require_normalized(meta)
        assert "?" not in normalized, f"query string leaked into normalized route: {normalized!r}"
        # `/headers` is also declared without parameters across weblogs.
        assert normalized == "/headers", f"expected '/headers', got {normalized!r}"
