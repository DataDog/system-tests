# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from urllib.parse import urlparse

from utils import context, BaseTestCase, interfaces, skipif


@skipif(context.weblog_variant == "echo-poc", reason="not relevant: echo isn't instrumented")
class Test_Meta(BaseTestCase):
    @skipif(
        context.library in ("python", "ruby", "golang", "php", "cpp",),
        reason="known bug: span.kind not included, should be discussed of actually a bug or not",
    )
    def test_meta_span_kind(self):
        """Validates that traces from an http framework carry a span.kind meta tag, with value server or client"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if span.get("type") != "web":  # do nothing if is not web related
                return

            if "span.kind" not in span["meta"]:
                raise Exception("web span expect an span.kind meta tag")

            if span["meta"]["span.kind"] not in ("server", "client"):
                raise Exception("Meta http.kind should be client or server")

            return True

        interfaces.library.add_span_validation(validator=validator)

    @skipif(
        context.library in ("ruby", "golang", "php"),
        reason="known bug: http.url is not a full url, should be discussed of actually a bug or not",
    )
    def test_meta_http_url(self):
        """Validates that traces from an http framework carry a http.url meta tag, formatted as a URL"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if span.get("type") != "web":  # do nothing if is not web related
                return

            if "http.url" not in span["meta"]:
                raise Exception("web span expect an http.url meta tag")

            scheme = urlparse(span["meta"]["http.url"]).scheme
            if scheme not in ("http", "https"):
                raise Exception(f"Meta http.url's scheme should be http or https, not {scheme}")

            return True

        interfaces.library.add_span_validation(validator=validator)

    @skipif(context.library == "ruby", reason="known bug: http.status_code is missing")
    def test_meta_http_status_code(self):
        """Validates that traces from an http framework carry a http.status_code meta tag, formatted as a int"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if span.get("type") != "web":  # do nothing if is not web related
                return

            if "http.status_code" not in span["meta"]:
                raise Exception("web span expect an http.status_code meta tag")

            _ = int(span["meta"]["http.status_code"])

            return True

        interfaces.library.add_span_validation(validator=validator)

    def test_meta_http_method(self):
        """Validates that traces from an http framework carry a http.method meta tag, with a legal HTTP method"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if span.get("type") != "web":  # do nothing if is not web related
                return

            if "http.method" not in span["meta"]:
                raise Exception("web span expect an http.method meta tag")

            value = span["meta"]["http.method"]

            if not isinstance(value, (str, bytes)):
                raise Exception("Method should always be a string")
            elif isinstance(value, bytes):
                value = value.decode("ascii")

            if value not in ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"):
                raise Exception("Unexpcted value for tag http.method")

            return True

        interfaces.library.add_span_validation(validator=validator)
