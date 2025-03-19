# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, bug, context, interfaces, rfc, features, missing_feature


def assert_tag_in_span_meta(span, tag, expected):
    if tag not in span["meta"]:
        raise Exception(f"Can't find {tag} in span's meta")

    val = span["meta"][tag]
    if val != expected:
        raise Exception(f"{tag} value is '{val}', should be '{expected}'")


def validate_identify_tags(tags):
    def inner_validate(span):
        for tag in tags:
            if isinstance(tags, dict):
                assert_tag_in_span_meta(span, tag, tags[tag])
            else:
                full_tag = f"usr.{tag}"
                assert_tag_in_span_meta(span, full_tag, full_tag)
        return True

    return inner_validate


@features.propagation_of_user_id_rfc
class Test_Basic:
    """Basic tests for Identify SDK"""

    def setup_identify_tags(self):
        # Send a request to the identify endpoint
        self.r = weblog.get("/identify")

    # reason for those three skip was :
    # DD_TRACE_HEADER_TAGS is not working properly, can't correlate request to trace
    @bug(context.library <= "golang@1.41.0", reason="APMRP-360")
    @bug(context.library < "nodejs@2.9.0", reason="APMRP-360")
    @bug(context.library <= "ruby@2.3.0", reason="APMRP-360")
    def test_identify_tags(self):
        interfaces.library.validate_spans(
            self.r, validator=validate_identify_tags(["id", "name", "email", "session_id", "role", "scope"])
        )

    def setup_identify_tags_with_attack(self):
        # Send a random attack on the identify endpoint - should not affect the usr.id tag
        self.r_with_attack = weblog.get("/identify", headers={"User-Agent": "Arachni/v1"})

    def test_identify_tags_with_attack(self):
        interfaces.library.validate_spans(
            self.r_with_attack, validator=validate_identify_tags(["id", "name", "email", "session_id", "role", "scope"])
        )


@rfc("https://docs.google.com/document/d/1T3qAE5nol18psOaHESQ3r-WRiZWss9nyGmroShug8ao/edit#heading=h.3wmduzc8mwe1")
@features.propagation_of_user_id_rfc
class Test_Propagate_Legacy:
    """Propagation tests for Identify SDK"""

    def setup_identify_tags_outgoing(self):
        # Send a request to the identify-propagate endpoint
        self.r_outgoing = weblog.get("/identify-propagate")

    @missing_feature(library="nodejs", reason="only supports incoming tags for now")
    @missing_feature(library="java", reason="only supports incoming tags for now")
    def test_identify_tags_outgoing(self):
        tag_table = {"_dd.p.usr.id": "dXNyLmlk"}
        interfaces.library.validate_spans(self.r_outgoing, validator=validate_identify_tags(tag_table))

    def setup_identify_tags_incoming(self):
        # Send a request to a generic endpoint, since any endpoint should propagate
        headers = {"x-datadog-trace-id": "1", "x-datadog-parent-id": "1", "x-datadog-tags": "_dd.p.usr.id=dXNyLmlk"}
        self.r_incoming = weblog.get("/waf", headers=headers)

    def test_identify_tags_incoming(self):
        """With W3C : this test expect to fail with DD_TRACE_PROPAGATION_STYLE_INJECT=W3C"""
        tag_table = {"_dd.p.usr.id": "dXNyLmlk"}
        interfaces.library.validate_spans(self.r_incoming, validator=validate_identify_tags(tag_table))


@rfc("https://docs.google.com/document/d/1T3qAE5nol18psOaHESQ3r-WRiZWss9nyGmroShug8ao/edit#heading=h.3wmduzc8mwe1")
@features.propagation_of_user_id_rfc
class Test_Propagate:
    """Propagation tests for Identify SDK"""

    def setup_identify_tags_outgoing(self):
        # Send a request to the identify-propagate endpoint
        self.r_outgoing = weblog.get("/identify-propagate")

    @missing_feature(library="nodejs", reason="only supports incoming tags for now")
    @missing_feature(library="java", reason="only supports incoming tags for now")
    def test_identify_tags_outgoing(self):
        tag_table = {"usr.id": "usr.id", "_dd.p.usr.id": "dXNyLmlk"}
        interfaces.library.validate_spans(self.r_outgoing, validator=validate_identify_tags(tag_table))

    def setup_identify_tags_incoming(self):
        # Send a request to a generic endpoint, since any endpoint should propagate
        headers = {"x-datadog-trace-id": "1", "x-datadog-parent-id": "1", "x-datadog-tags": "_dd.p.usr.id=dXNyLmlk"}
        self.r_incoming = weblog.get("/waf", headers=headers)

    def test_identify_tags_incoming(self):
        """With W3C : this test expect to fail with DD_TRACE_PROPAGATION_STYLE_INJECT=W3C"""

        def usr_id_not_present(span):
            if "usr.id" in span["meta"]:
                raise Exception("usr.id must not be present in this span")
            return True

        tag_table = {"_dd.p.usr.id": "dXNyLmlk"}
        interfaces.library.validate_spans(self.r_incoming, validator=validate_identify_tags(tag_table))
        interfaces.library.validate_spans(self.r_incoming, validator=usr_id_not_present)
