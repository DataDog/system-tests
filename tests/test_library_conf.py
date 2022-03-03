# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, BaseTestCase, interfaces, released, bug, irrelevant, missing_feature

# PHP JAVA ok


@irrelevant(library="cpp")
@released(golang="1.36.0", dotnet="2.1.0", nodejs="2.0.0", php="0.68.2", python="0.53")
@missing_feature(context.library <= "golang@1.36.2" and context.weblog_variant == "gin")
class Test_HeaderTags(BaseTestCase):
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags(self):
        tag_conf = context.weblog_image.env["DD_TRACE_HEADER_TAGS"]  # TODO: split by comma
        _, tag_name = tag_conf.split(":")

        interfaces.library.add_span_validation(validator=lambda span: tag_name in span.get("meta", {}))
