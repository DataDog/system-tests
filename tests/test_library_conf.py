# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, BaseTestCase, interfaces, released, bug, irrelevant, missing_feature
from utils.tools import logger

# PHP JAVA ok


# basic / legacy tests, just tests user-agent can be received as a tag
@irrelevant(library="cpp")
@released(golang="?", dotnet="?", nodejs="?", php="0.68.2", python="0.53")
@coverage.basic
class Test_HeaderTags(BaseTestCase):
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags_basic(self):
        def validator(span):
            if span.get("type") == "web":
                assert "http.request.headers.user-agent" in span.get("meta", {})

        interfaces.library.add_span_validation(validator=validator, is_success_on_expiry=True)
