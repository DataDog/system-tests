# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, bug, context, interfaces, released, coverage, rfc
import pytest
import base64

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


def assertTagInSpanMeta(span, tag, expected):
    if tag not in span["meta"]:
        raise Exception(f"Can't find {tag} in span's meta")

    val = span["meta"][tag]
    if val != expected:
        raise Exception(f"{tag} value is '{val}', should be '{expected}'")


def validate_identify_tags(tags):
    def inner_validate(span):
        for tag in tags:
            if type(tags) is dict:
                assertTagInSpanMeta(span, tag, tags[tag])
            else:
                fullTag = f"usr.{tag}"
                assertTagInSpanMeta(span, fullTag, fullTag)
        return True

    return inner_validate


@released(dotnet="2.7.0", golang="1.37.0", java="?", nodejs="2.4.0", php="0.72.0", python="?", ruby="1.0.0")
@coverage.basic
class Test_Basic(BaseTestCase):
    """Basic tests for Identify SDK"""

    @bug(library="golang", reason="DD_TRACE_HEADER_TAGS is not working properly, can't correlate request to trace")
    @bug(
        context.library < "nodejs@2.9.0",
        reason="DD_TRACE_HEADER_TAGS is not working properly, can't correlate request to trace",
    )
    @bug(library="ruby", reason="DD_TRACE_HEADER_TAGS is not working properly, can't correlate request to trace")
    def test_identify_tags(self):
        # Send a request to the identify endpoint
        r = self.weblog_get("/identify")
        interfaces.library.add_span_validation(
            r, validate_identify_tags(["id", "name", "email", "session_id", "role", "scope"])
        )

    def test_identify_tags_with_attack(self):
        # Send a random attack on the identify endpoint - should not affect the usr.id tag
        r = self.weblog_get("/identify", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.add_span_validation(
            r, validate_identify_tags(["id", "name", "email", "session_id", "role", "scope"])
        )


@rfc("https://docs.google.com/document/d/1T3qAE5nol18psOaHESQ3r-WRiZWss9nyGmroShug8ao/edit#heading=h.3wmduzc8mwe1")
@released(dotnet="2.11.0", golang="?", java="?", nodejs="?", php="0.76.0", python="?", ruby="?")
@coverage.basic
class Test_Propagate(BaseTestCase):
    """Propagation tests for Identify SDK"""

    def test_identify_tags_outgoing(self):
        tagTable = {"_dd.p.usr.id": "dXNyLmlk"}

        # Send a request to the identify-propagate endpoint
        r = self.weblog_get("/identify-propagate")
        interfaces.library.add_span_validation(r, validate_identify_tags(tagTable))

    def test_identify_tags_incoming(self):
        tagTable = {"_dd.p.usr.id": "dXNyLmlk"}

        # Send a request to a generic endpoint, since any endpoint should propagate
        headers = {"x-datadog-trace-id": "1", "x-datadog-parent-id": "1", "x-datadog-tags": "_dd.p.usr.id=dXNyLmlk"}
        r = self.weblog_get("/waf", headers=headers)
        interfaces.library.add_span_validation(r, validate_identify_tags(tagTable))
