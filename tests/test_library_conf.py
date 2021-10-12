# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, BaseTestCase, interfaces, skipif

# PHP JAVA ok


@skipif(context.library == "cpp", reason="not relevant")
@skipif(context.library == "dotnet", reason="known bug: .NET replaces dot by underscores: XXXXX")
@skipif(context.weblog_variant == "echo-poc", reason="Not relevant: echo is not instrumented")
@skipif(context.library == "golang", reason="missing feature")
@skipif(context.library == "nodejs", reason="missing feature")
@skipif(context.library == "php", reason="missing feature: partial support, can't set the key")
@skipif(context.library < "python@0.53", reason="Not relevant: Implemented in 0.53")
@skipif(context.library == "ruby", reason="missing feature")
class Test_HeaderTags(BaseTestCase):
    def test_trace_header_tags(self):
        """DD_TRACE_HEADER_TAGS env var support"""
        tag_conf = context.weblog_image.env["DD_TRACE_HEADER_TAGS"]  # TODO: split by comma
        _, tag_name = tag_conf.split(":")

        interfaces.library.add_span_validation(validator=lambda span: tag_name in span.get("meta", {}))
