# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, coverage
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(dotnet="2.7.0", golang="1.37.0", java="?", nodejs="2.4.0", php="0.72.0", python="?", ruby="1.0.0")
@coverage.basic
class Test_Basic(BaseTestCase):
    """ Basic tests for Identify SDK """

    def test_identify_tags(self):
        def assertTagInSpanMeta(span, tag):
            if tag not in span["meta"]:
                raise Exception(f"Can't find {tag} in span's meta")

            val = span["meta"][tag]
            if val != tag:
                raise Exception(f"{tag} value is '{val}', should be '{tag}'")

        def validate_identify_tags(span):
            for tag in ["id", "name", "email", "session_id", "role", "scope"]:
                assertTagInSpanMeta(span, f"usr.{tag}")
            return True

        # Send a random attack on the identify endpoint
        r = self.weblog_get("/identify", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.add_span_validation(r, validate_identify_tags)
