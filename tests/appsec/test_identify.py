# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest

from tests.constants import PYTHON_RELEASE_GA_1_1
from utils import weblog, context, coverage, interfaces, released

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(dotnet="2.7.0", golang="1.37.0", java="?", nodejs="2.4.0")
@released(php="0.72.0", python=PYTHON_RELEASE_GA_1_1, ruby="1.0.0")
@coverage.basic
class Test_Basic:
    """Basic tests for Identify SDK for AppSec"""

    def setup_identify_tags_with_attack(self):
        self.r = weblog.get("/identify", headers={"User-Agent": "Arachni/v1"})

    def test_identify_tags_with_attack(self):
        # Send a random attack on the identify endpoint - should not affect the usr.id tag

        def validate_identify_tags(span):
            for tag in ["id", "name", "email", "session_id", "role", "scope"]:
                key = f"usr.{tag}"
                assert key in span["meta"], f"Can't find {key} in span's meta"

                expected_value = f"usr.{tag}"  # key and value are the same on weblog spec
                value = span["meta"][key]
                if value != expected_value:
                    raise Exception(f"{key} value is '{value}', should be '{expected_value}'")

            return True

        interfaces.library.validate_spans(self.r, validate_identify_tags)
