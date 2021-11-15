# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, BaseTestCase, interfaces, released, bug, irrelevant, missing_feature

# PHP JAVA ok


@irrelevant(library="cpp")
@bug(library="dotnet", reason=".NET replaces dot by underscores: XXXXX")
@missing_feature(library="golang")
@missing_feature(library="nodejs")
@missing_feature(library="php", reason="partial support, can't set the key")
@released(python="0.53")
@missing_feature(library="ruby")
class Test_HeaderTags(BaseTestCase):
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags(self):
        tag_conf = context.weblog_image.env["DD_TRACE_HEADER_TAGS"]  # TODO: split by comma
        _, tag_name = tag_conf.split(":")

        interfaces.library.add_span_validation(validator=lambda span: tag_name in span.get("meta", {}))
