# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re
from urllib.parse import urlparse

from utils import context, BaseTestCase, interfaces, bug

RUNTIME_LANGUAGE_MAP = {
    "nodejs": "javascript",
    "golang": "go",
}
VARIANT_COMPONENT_MAP = {
    "flask-poc": "flask",
    "express4": "express",
    "express4-typescript": "express",
    "uwsgi-poc": "flask",
    "django-poc": "django",
    "gorilla": "gorilla/mux",
    "jersey-grizzly2": {"jakarta-rs.request": "jakarta-rs-controller", "grizzly.request": ["grizzly", "jakarta-rs"]},
    "net-http": "net/http",
    "sinatra": {"rack.request": "rack"},
    "spring-boot": {
        "servlet.request": "tomcat-server",
        "spring.handler": "spring-web-controller",
        "servlet.forward": "java-web-servlet-dispatcher",
    },
    "spring-boot-jetty": {
        "servlet.request": "jetty-server",
        "spring.handler": "spring-web-controller",
        "servlet.forward": "java-web-servlet-dispatcher",
    },
    "spring-boot-openliberty": {
        "servlet.request": ["liberty-server", "java-web-servlet"],
        "spring.handler": "spring-web-controller",
        "servlet.forward": "java-web-servlet-dispatcher",
    },
    "resteasy-netty3": {"netty.request": ["netty", "jax-rs"], "jax-rs.request": "jax-rs-controller",},
    "rails": {
        "rails.action_controller": "action_pack",
        "rails.render_template": "action_view",
        "rack.request": "rack",
        "sinatra.request": "sinatra",
    },
    "ratpack": {"ratpack.handler": "ratpack", "netty.request": "netty"},
    "vertx3": {"netty.request": "netty", "vertx.route-handler": "vertx"},
}


def get_component_name(weblog_variant, language, span_name):
    if language == "ruby":
        # strip numbers from weblog_variant so rails70 -> rails, sinatra14 -> sinatra
        weblog_variant_stripped_name = re.sub(r"\d+", "", weblog_variant)
        expected_component = VARIANT_COMPONENT_MAP.get(weblog_variant_stripped_name, weblog_variant_stripped_name)
    elif language == "dotnet":
        expected_component = "aspnet_core"
    elif language == "cpp":
        expected_component = "nginx"
    else:
        # using weblog variant to get name of component that should be on set within each span's metadata
        expected_component = VARIANT_COMPONENT_MAP.get(weblog_variant, weblog_variant)

    # if type of component is a dictionary, get the component tag value by searching dict with current span name
    # try to get component name from name of span, otherwise use beginning of span as expected component, e.g: 'rack' for span name 'rack.request'
    if type(expected_component) is dict:
        expected_component = expected_component.get(span_name, span_name.split(".")[0])
    return expected_component


class Test_Meta(BaseTestCase):
    """meta object in spans respect all conventions"""

    @bug(library="ruby", reason="Span.kind not implemented yet")
    @bug(library="php", reason="Span.kind not implemented yet")
    @bug(library="cpp", reason="Span.kind said to be implemented but currently not set for nginx")
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

    @bug(library="ruby", reason="http.url is not a full url, should be discussed of actually a bug or not")
    @bug(library="golang", reason="http.url is not a full url, should be discussed of actually a bug or not")
    @bug(context.library < "php@0.68.2")
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

            if isinstance(value, bytes):
                value = value.decode("ascii")

            if value not in ("GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS", "TRACE", "PATCH"):
                raise Exception(f"Unexpcted value '{value}' for tag http.method")

            return True

        interfaces.library.add_span_validation(validator=validator)

    @bug(library="php", reason="language tag not implemented")
    @bug(library="ruby", reason="language tag not implemented")
    @bug(library="cpp", reason="language tag not implemented")
    @bug(library="java", reason="language tag being set on all spans including client and producer spans")
    def test_meta_language_tag(self):
        """Assert that all spans have required language tag."""

        def validator(span):
            library = context.library.library

            # if span.kind is client or producer we should not set language tag
            if span["meta"].get("span.kind") in ["client", "producer"]:
                if span["meta"].get("language") is not None:
                    raise Exception(
                        "Span should not have language tag set with span.kind of {}.".format(span["meta"]["span.kind"])
                    )

            # else we should set the language tag
            elif RUNTIME_LANGUAGE_MAP.get(library, library) != span["meta"]["language"]:
                raise Exception(
                    "Span actual language, {}, did not match expected language, {}.".format(
                        span["meta"]["language"], RUNTIME_LANGUAGE_MAP.get(library, library)
                    )
                )
            return True

        interfaces.library.add_span_validation(validator=validator)

    @bug(library="php", reason="component tag not implemented")
    def test_meta_component_tag(self):
        """Assert that all spans generated from a weblog_variant have component metadata tag matching integration name."""

        def validator(span):
            if span.get("type") != "web":  # do nothing if is not web related
                return

            expected_component = get_component_name(context.weblog_variant, context.library, span.get("name"))

            if "component" not in span.get("meta"):
                raise Exception(f"No component tag found. Expected span component to be: {expected_component}.")

            actual_component = span.get("meta")["component"]

            if type(expected_component) is list:
                if actual_component not in expected_component:
                    raise Exception(
                        f"Expected span to have component meta tag equal to one of the following, [{expected_component}], got: {actual_component}."
                    )
            else:
                if actual_component != expected_component:
                    raise Exception(
                        f"Expected span to have component meta tag, {expected_component}, got: {actual_component}."
                    )
            return True

        interfaces.library.add_span_validation(validator=validator)


@bug(
    context.library in ("cpp", "python", "ruby"),
    reason="Inconsistent implementation across tracers; will need a dedicated testing scenario",
)
class Test_MetaDatadogTags(BaseTestCase):
    """Spans carry meta tags that were set in DD_TAGS tracer environment"""

    def test_meta_dd_tags(self):
        def validator(span):
            if span["meta"]["key1"] != "val1":
                raise Exception(f'keyTag tag in span\'s meta should be "test", not {span["meta"]["env"]}')

            if span["meta"]["key2"] != "val2":
                raise Exception(f'dKey tag in span\'s meta should be "key2:val2", not {span["meta"]["key2"]}')

            return True

        interfaces.library.add_span_validation(validator=validator)


class Test_MetricsStandardTags(BaseTestCase):
    """metrics object in spans respect all conventions regarding basic tags"""

    @bug(library="cpp", reason="Not implemented")
    @bug(library="java", reason="Not implemented")
    @bug(library="php", reason="Currently system.pid")
    @bug(library="ruby", reason="Currently system.pid")
    def test_metrics_process_id(self):
        """Validates that root spans from traces contain a process_id field"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if "process_id" not in span["metrics"]:
                raise Exception("web span expect a process_id metrics tag")

            return True

        interfaces.library.add_span_validation(validator=validator)
