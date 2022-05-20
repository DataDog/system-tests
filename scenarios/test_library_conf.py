# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, coverage, BaseTestCase, interfaces, released, bug, irrelevant, missing_feature
from utils.tools import logger

# PHP JAVA ok


@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@coverage.basic
class Test_HeaderTagsShortFormat(BaseTestCase):
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags(self):
        tag_conf = context.weblog_image.env["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        tag_config_list = full_tag_config_list[1::]

        headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        tags = {"http.request.headers." + tag: headers[tag] for tag in tag_config_list}

        r = self.weblog_get(f"/waf", headers=headers)
        interfaces.library.add_span_tag_validation(request=r, tags=tags)


@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="?", nodejs="?", php_appsec="?", python="?", ruby="?")
@coverage.basic
class Test_HeaderTagsLongFormat(BaseTestCase):
    def test_trace_header_tags(self):
        tag_conf = context.weblog_image.env["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        tag_config_list = full_tag_config_list[1::]

        headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        tags = {item.split(":")[1]: headers[item.split(":")[0]] for item in tag_config_list}

        r = self.weblog_get(f"/waf", headers=headers)
        interfaces.library.add_span_tag_validation(request=r, tags=tags)
