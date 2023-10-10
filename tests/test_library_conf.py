# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re
from utils import coverage, weblog, interfaces, irrelevant, scenarios, bug

# basic / legacy tests, just tests user-agent can be received as a tag
@irrelevant(library="cpp")
@coverage.basic
class Test_HeaderTags:
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags_basic(self):
        """ Test that http.request.headers.user-agent is in all web spans """

        for _, span in interfaces.library.get_root_spans():
            if span.get("type") == "web":
                assert "http.request.headers.user-agent" in span.get("meta", {})

# Should "irrelevant" tests go in the cpp.yaml with "missing_feature"?
@irrelevant(library="cpp")
@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTagsShortFormat:
    """Validates that the short, header name only, format for specifying headers correctly tags spans"""
    def setup_trace_header_tags(self):
        self.headers = {'header1': "val"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_header_tags.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, which is always the user-agent header
        tag_config_list = full_tag_config_list[1::]
        # 'header1' should be the first item in the list now
        header = tag_config_list[0]
        tags = {"http.request.headers." + header: self.headers[header]}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@irrelevant(library="cpp")
@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTagsLongFormat:
    """Validates that tracer uses `<header>:<tag_name>` format correctly tags spans"""
    test_num = 2

    def setup_trace_header_tags(self):
        self.headers = {f"header{Test_HeaderTagsLongFormat.test_num}": "val"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_header_tags.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, which is always the user-agent header
        tag_config_list = full_tag_config_list[1::]
        # 'header2' should be the second item in the list now
        header_tag = tag_config_list[1]
        tags = {header_tag.split(":")[1]: self.headers[header_tag.split(":")[0]]}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@irrelevant(library="cpp")
@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTagsWhitespacing_Headers:
    """Validates that leading/trailing whitespaces are trimmed on the header values given to DD_TRACE_HEADER_TAGS
    e.g, ' header ' in DD_TRACE_HEADER_TAGS=' header ' becomes 'header' and is expected to match req.header of 'header' """

    def setup_trace_header_tags(self):
        self.headers = {"header3": "val"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_header_tags.weblog_container.environment[
            "DD_TRACE_HEADER_TAGS"
        ]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, which is always the user-agent header
        tag_config_list = full_tag_config_list[1::]
        # ' header3 ' should be the third item in the list now
        header_tag = tag_config_list[2].strip()
        val = self.headers[header_tag]
        tags = {"http.request.headers." + header_tag: val}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


# Note: dotnet fails this test. It normalizes those spaces to underscores instead.
@irrelevant(library="cpp")

@coverage.basic
@bug(library="dotnet", reason="https://datadoghq.atlassian.net/browse/AIT-8308")
@scenarios.library_conf_custom_header_tags
class Test_HeaderTagsWhitespacing_Tags:
    """Validates that leading/trailing whitespaces on the input to DD_TRACE_HEADER_TAGS are 
    trimmed on mapping parts, but whitespaces in between non-whitespace chars are left in-tact."""

    def setup_trace_header_tags(self):
        self.headers = {"header4": "val"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_header_tags.weblog_container.environment[
            "DD_TRACE_HEADER_TAGS"
        ]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, which is always the user-agent header
        tag_config_list = full_tag_config_list[1::]
        # 'header4' should be the fourth item in the list now
        header_tag = tag_config_list[3]
        tags = {header_tag.split(":")[1].strip(): self.headers[header_tag.split(":")[0]]}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@irrelevant(library="cpp")

@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTagsWhitespacing_Vals:
    """Validates that whitespaces in header values are not removed in the span tag value"""

    def setup_trace_header_tags(self):
        self.headers = {"header5": " val"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_header_tags.weblog_container.environment[
            "DD_TRACE_HEADER_TAGS"
        ]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, which is always the user-agent header
        tag_config_list = full_tag_config_list[1::]
        # 'header5' should be the fifth item in the list now
        header_tag = tag_config_list[4]
        tags = {"http.request.headers." + header_tag: self.headers["header5"].strip()}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@irrelevant(library="cpp")
@coverage.basic
@bug(library="golang", reason="https://datadoghq.atlassian.net/browse/AIT-8571")
@scenarios.library_conf_custom_header_tags
class Test_HeaderTagsColon_Edge:
    """ Validates that input to DD_TRACE_HEADER_TAGS with leading & trailing
    colons is still considered a tag mapping input """

    def setup_trace_header_tags(self):
        self.headers = {"header6": "val6", "header7": "val7"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_header_tags.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, which is always the user-agent header
        tag_config_list = full_tag_config_list[1::]
        # ':header6' and 'header7:' should be the sixth and seventh items in the list now
        header_tags = [tag_config_list[5], tag_config_list[6]]
        nottags = []
        for item in header_tags:
            nottags.append("http.request.headers." + item)
            splitItem = item.split(":")
            nottags.append(splitItem[0])
            nottags.append(splitItem[1])

        interfaces.library.add_not_span_tag_validation(request=self.r, nottags=nottags)
