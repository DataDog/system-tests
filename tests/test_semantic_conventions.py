# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re
from urllib.parse import urlparse

from utils import context, interfaces, bug, released

RUNTIME_LANGUAGE_MAP = {
    "nodejs": "javascript",
    "golang": "go",
    "java": "jvm",
}

"""
map of weblog_variant_name to expected integration (component) name
if value type is list, then multiple component names are possible, ie two versions of one integration, see chi
if value is dict, the weblog variant has multiple spans each with a different expected component name
"""
VARIANT_COMPONENT_MAP = {
    "chi": ["go-chi/chi", "go-chi/chi.v5"],
    "flask-poc": "flask",
    "echo": ["labstack/echo.v4", "labstack/echo"],
    "express4": "express",
    "express4-typescript": "express",
    "uwsgi-poc": "flask",
    "django-poc": "django",
    "gin": "gin-gonic/gin",
    "gorilla": "gorilla/mux",
    "jersey-grizzly2": {"jakarta-rs.request": "jakarta-rs-controller", "grizzly.request": ["grizzly", "jakarta-rs"]},
    "net-http": "net/http",
    "sinatra": {"rack.request": "rack"},
    "spring-boot": {
        "servlet.request": "tomcat-server",
        "hsqldb.query": ["java-jdbc-prepared_statement", "java-jdbc-statement"],
        "spring.handler": "spring-web-controller",
        "servlet.forward": "java-web-servlet-dispatcher",
        "servlet.response": "java-web-servlet-response",
        "grpc.server": "grpc-server",
    },
    "spring-boot-jetty": {
        "servlet.request": "jetty-server",
        "hsqldb.query": "java-jdbc-statement",
        "spring.handler": "spring-web-controller",
        "servlet.forward": "java-web-servlet-dispatcher",
        "servlet.response": "java-web-servlet-response",
    },
    "spring-boot-3-native": {
        "servlet.request": "tomcat-server",
        "hsqldb.query": "java-jdbc-statement",
        "servlet.response": "java-web-servlet-response",
    },
    "spring-boot-native": {
        "servlet.request": "tomcat-server",
        "hsqldb.query": "java-jdbc-statement",
        "spring.handler": "spring-web-controller",
        "servlet.forward": "java-web-servlet-dispatcher",
        "servlet.include": "java-web-servlet-dispatcher",
        "servlet.response": "java-web-servlet-response",
    },
    "spring-boot-openliberty": {
        "servlet.request": ["liberty-server", "java-web-servlet"],
        "hsqldb.query": "java-jdbc-statement",
        "spring.handler": "spring-web-controller",
        "servlet.forward": "java-web-servlet-dispatcher",
        "servlet.response": "java-web-servlet-response",
    },
    "spring-boot-undertow": {
        "servlet.request": "undertow-http-server",
        "hsqldb.query": "java-jdbc-statement",
        "spring.handler": "spring-web-controller",
        "undertow-http.request": "undertow-http-server",
        "servlet.response": "java-web-servlet-response",
    },
    "spring-boot-wildfly": {
        "servlet.request": "undertow-http-server",
        "hsqldb.query": "java-jdbc-statement",
        "undertow-http.request": "undertow-http-server",
        "servlet.forward": "java-web-servlet-dispatcher",
        "spring.handler": "spring-web-controller",
        "servlet.response": "java-web-servlet-response",
    },
    "resteasy-netty3": {"netty.request": ["netty", "jax-rs"], "jax-rs.request": "jax-rs-controller",},
    "rails": {
        "rails.action_controller": "action_pack",
        "rails.render_template": "action_view",
        "rack.request": "rack",
        "sinatra.request": "sinatra",
    },
    "ratpack": {"ratpack.handler": "ratpack", "netty.request": "netty"},
    "uds-echo": "labstack/echo.v4",
    "uds-express4": "express",
    "uds-flask": {"flask.request": "flask",},
    "uds-sinatra": {"rack.request": "rack", "sinatra.route": "sinatra", "sinatra.request": "sinatra",},
    "uds-spring-boot": {
        "servlet.request": "tomcat-server",
        "hsqldb.query": "java-jdbc-statement",
        "spring.handler": "spring-web-controller",
        "servlet.forward": "java-web-servlet-dispatcher",
    },
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
    if isinstance(expected_component, dict):
        expected_component = expected_component.get(span_name, span_name.split(".")[0])
    return expected_component


class Test_Meta:
    """meta object in spans respect all conventions"""

    @bug(library="cpp", reason="Span.kind said to be implemented but currently not set for nginx")
    @bug(library="python", reason="Span.kind not implemented yet")
    @bug(library="php", reason="All PHP current weblog variants trace with C++ tracers that do not have Span.Kind")
    def test_meta_span_kind(self):
        """Validates that traces from an http framework carry a span.kind meta tag, with value server or client"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if span.get("type") != "web":  # do nothing if is not web related
                return

            assert "span.kind" in span["meta"], "Web span expects a span.kind meta tag"
            assert span["meta"]["span.kind"] in ["server", "client"], "Meta tag span.kind should be client or server"

            return True

        interfaces.library.validate_spans(validator=validator)

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

            assert "http.url" in span["meta"], "web span expect an http.url meta tag"

            scheme = urlparse(span["meta"]["http.url"]).scheme
            assert scheme in ["http", "https"], f"Meta http.url's scheme should be http or https, not {scheme}"

            return True

        interfaces.library.validate_spans(validator=validator)

    def test_meta_http_status_code(self):
        """Validates that traces from an http framework carry a http.status_code meta tag, formatted as a int"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if span.get("type") != "web":  # do nothing if is not web related
                return

            assert "http.status_code" in span["meta"], "web span expect an http.status_code meta tag"

            _ = int(span["meta"]["http.status_code"])

            return True

        interfaces.library.validate_spans(validator=validator)

    def test_meta_http_method(self):
        """Validates that traces from an http framework carry a http.method meta tag, with a legal HTTP method"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if span.get("type") != "web":  # do nothing if is not web related
                return

            assert "http.method" in span["meta"], "web span expect an http.method meta tag"

            value = span["meta"]["http.method"]

            assert isinstance(value, (str, bytes)), "Method should always be a string"

            if isinstance(value, bytes):
                value = value.decode("ascii")

            assert value in [
                "GET",
                "HEAD",
                "POST",
                "PUT",
                "DELETE",
                "OPTIONS",
                "TRACE",
                "PATCH",
            ], f"Unexpcted value '{value}' for tag http.method"

            return True

        interfaces.library.validate_spans(validator=validator)

    @bug(library="cpp", reason="language tag not implemented")
    @bug(library="php", reason="language tag not implemented")
    @released(python="1.80.0")
    @bug(library="java", reason="language tag implemented but not for all spans")
    def test_meta_language_tag(self):
        """Assert that all spans have required language tag."""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            assert "language" in span["meta"], "Span must have a language tag set."

            library = context.library.library
            expected_language = RUNTIME_LANGUAGE_MAP.get(library, library)

            actual_language = span["meta"]["language"]
            assert (
                actual_language == expected_language
            ), f"Span actual language, {actual_language}, did not match expected language, {expected_language}."

        interfaces.library.validate_spans(validator=validator, success_by_default=True)
        # checking that we have at least one root span
        assert len(list(interfaces.library.get_root_spans())) != 0, "Did not recieve any root spans to validate."

    @bug(library="php", reason="component tag not implemented for apache-mode and php-fpm")
    @released(python="1.80.0")
    def test_meta_component_tag(self):
        """Assert that all spans generated from a weblog_variant have component metadata tag matching integration name."""

        def validator(span):
            if span.get("type") != "web":  # do nothing if is not web related
                return

            expected_component = get_component_name(context.weblog_variant, context.library, span.get("name"))

            assert "component" in span.get(
                "meta"
            ), f"No component tag found. Expected span {span['name']} component to be: {expected_component}."
            actual_component = span.get("meta")["component"]

            if isinstance(expected_component, list):
                exception_message = f"""Expected span {span['name']} to have component meta tag equal
                 to one of the following, [{expected_component}], got: {actual_component}."""

                assert actual_component in expected_component, exception_message
            else:
                exception_message = f"Expected span {span['name']} to have component meta tag, {expected_component}, got: {actual_component}."
                assert actual_component == expected_component, exception_message

        interfaces.library.validate_spans(validator=validator, success_by_default=True)
        # checking that we have at least one root span
        assert len(list(interfaces.library.get_root_spans())) != 0, "Did not recieve any root spans to validate."

    @bug(library="cpp", reason="runtime-id tag not implemented")
    @bug(library="php", reason="runtime-id tag only implemented when profiling is enabled.")
    def test_meta_runtime_id_tag(self):
        """Assert that all spans generated from a weblog_variant have runtime-id metadata tag with some value."""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            assert "runtime-id" in span.get("meta"), "No runtime-id tag found. Expected tag to be present."

        interfaces.library.validate_spans(validator=validator, success_by_default=True)
        # checking that we have at least one root span
        assert len(list(interfaces.library.get_root_spans())) != 0, "Did not recieve any root spans to validate."


@bug(
    context.library in ("cpp", "python", "ruby"),
    reason="Inconsistent implementation across tracers; will need a dedicated testing scenario",
)
class Test_MetaDatadogTags:
    """Spans carry meta tags that were set in DD_TAGS tracer environment"""

    def test_meta_dd_tags(self):
        def validator(span):
            assert (
                span["meta"]["key1"] == "val1"
            ), f'keyTag tag in span\'s meta should be "test", not {span["meta"]["env"]}'
            assert (
                span["meta"]["key2"] == "val2"
            ), f'dKey tag in span\'s meta should be "key2:val2", not {span["meta"]["key2"]}'

            return True

        interfaces.library.validate_spans(validator=validator)


class Test_MetricsStandardTags:
    """metrics object in spans respect all conventions regarding basic tags"""

    @bug(library="cpp", reason="Not implemented")
    def test_metrics_process_id(self):
        """Validates that root spans from traces contain a process_id field"""

        def validator(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            assert "process_id" in span["metrics"], "Root span expect a process_id metrics tag"

        interfaces.library.validate_spans(validator=validator, success_by_default=True)
        # checking that we have at least one root span
        assert len(list(interfaces.library.get_root_spans())) != 0, "Did not recieve any root spans to validate."
