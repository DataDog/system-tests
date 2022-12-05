# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest

from tests.constants import PYTHON_RELEASE_GA_1_1
from utils import weblog, bug, context, coverage, interfaces, released, rfc

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
            if isinstance(tags, dict):
                assertTagInSpanMeta(span, tag, tags[tag])
            else:
                fullTag = f"usr.{tag}"
                assertTagInSpanMeta(span, fullTag, fullTag)
        return True

    return inner_validate


@released(dotnet="2.7.0", golang="1.37.0", java="?", nodejs="2.4.0", php="0.72.0")
@released(python=PYTHON_RELEASE_GA_1_1, ruby="1.0.0")
@coverage.basic
class Test_Basic:
    """Basic tests for Identify SDK"""

    def setup_identify_tags(self):
        # Send a request to the identify endpoint
        self.r = weblog.get("/identify")

    @bug(
        context.library <= "golang@1.41.0",
        reason="DD_TRACE_HEADER_TAGS is not working properly, can't correlate request to trace",
    )
    @bug(
        context.library < "nodejs@2.9.0",
        reason="DD_TRACE_HEADER_TAGS is not working properly, can't correlate request to trace",
    )
    @bug(library="ruby", reason="DD_TRACE_HEADER_TAGS is not working properly, can't correlate request to trace")
    def test_identify_tags(self):
        interfaces.library.validate_spans(
            self.r, validate_identify_tags(["id", "name", "email", "session_id", "role", "scope"])
        )

    def setup_identify_tags_with_attack(self):
        # Send a random attack on the identify endpoint - should not affect the usr.id tag
        self.r_with_attack = weblog.get("/identify", headers={"User-Agent": "Arachni/v1"})

    def test_identify_tags_with_attack(self):
        interfaces.library.validate_spans(
            self.r_with_attack, validate_identify_tags(["id", "name", "email", "session_id", "role", "scope"])
        )


@rfc("https://docs.google.com/document/d/1T3qAE5nol18psOaHESQ3r-WRiZWss9nyGmroShug8ao/edit#heading=h.3wmduzc8mwe1")
@released(dotnet="?", golang="1.41.0", java="?", nodejs="?", php="0.76.0", python=PYTHON_RELEASE_GA_1_1, ruby="?")
@coverage.basic
class Test_Propagate:
    """Propagation tests for Identify SDK"""

    def setup_identify_tags_outgoing(self):
        # Send a request to the identify-propagate endpoint
        self.r_outgoing = weblog.get("/identify-propagate")

    def test_identify_tags_outgoing(self):
        tagTable = {"_dd.p.usr.id": "dXNyLmlk"}
        interfaces.library.validate_spans(self.r_outgoing, validate_identify_tags(tagTable))

    def setup_identify_tags_incoming(self):
        # Send a request to a generic endpoint, since any endpoint should propagate
        headers = {"x-datadog-trace-id": "1", "x-datadog-parent-id": "1", "x-datadog-tags": "_dd.p.usr.id=dXNyLmlk"}
        self.r_incoming = weblog.get("/waf", headers=headers)

    def test_identify_tags_incoming(self):
        """ with W3C : this test expect to fail with DD_TRACE_PROPAGATION_STYLE_INJECT=W3C """
        tagTable = {"_dd.p.usr.id": "dXNyLmlk"}
        interfaces.library.validate_spans(self.r_incoming, validate_identify_tags(tagTable))
