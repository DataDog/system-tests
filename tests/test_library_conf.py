# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, weblog, interfaces, released, irrelevant, scenarios


# basic / legacy tests, just tests user-agent can be received as a tag
@irrelevant(library="cpp")
@released(dotnet="?", golang="?", java="?", nodejs="?", php="0.68.2", python="0.53", ruby="?")
@coverage.basic
class Test_HeaderTags:
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags_basic(self):
        """ Test that http.request.headers.user-agent is in all web spans """

        for _, _, span in interfaces.library.get_spans():
            if span.get("type") == "web":
                assert "http.request.headers.user-agent" in span.get("meta", {})


@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="1.10.0", nodejs="3.15.0", php="0.74.0", python="?", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_short
class Test_HeaderTagsShortFormat:
    """Validates that the short, header name only, format for specifying headers correctly tags spans"""

    def setup_trace_header_tags(self):
        self.headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_headers_short.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        # full_tag_config_list = ["header-tag1", "header-tag2"]
        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        # tag_config_list = ["header-tag2"]
        tag_config_list = full_tag_config_list[1::]

        # tags = {http.request.headers.header-tag2 : header-val2}
        tags = {"http.request.headers." + tag: self.headers[tag] for tag in tag_config_list}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


# MTOFF: Confirmed that these tests split at the first colon
# Next, test input with whitespacing as tests don't specify -- specifically around the first colon
@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="?", python="1.2.1", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_long
class Test_HeaderTagsLongFormat:
    """Validates that the short, header : tag name, format for specifying headers correctly tags spans"""

    #send request with headers listed in self.headers
    def setup_trace_header_tags(self):
        self.headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        # DD_TRACE_HEADER_TAGS= header-tag1:custom.header-tag1, header-tag2:custom.header-tag2
        tag_conf = scenarios.library_conf_custom_headers_long.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        # full_tag_config_list = ["header-tag1:custom.header-tag1", "header-tag2:custom.header-tag2"]
        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        # tag_config_list = ["header-tag2:custom.header-tag2"]
        tag_config_list = full_tag_config_list[1::]

        # tags = {custom.header-tag2: self.headers[header-tag2]}
        # tags = {custom.header-tag2: header-val2}
        tags = {item.split(":")[1]: self.headers[item.split(":")[0]] for item in tag_config_list}
        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="?", python="1.2.1", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_long
class Test_HeaderTagsNormalization:
    """Validates that the short, header : tag name, format for specifying headers correctly tags spans"""

    #send request with headers listed in self.headers
    def setup_trace_header_tags(self):
        self.headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        # DD_TRACE_HEADER_TAGS=" header-tag1:custom.header-tag1, header-tag2:custom.header-tag2"
        tag_conf = scenarios.library_conf_custom_headers_norm.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        # full_tag_config_list = ["header-tag1:custom.header-tag1", "header-tag2:custom.header-tag2"]
        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        # tag_config_list = ["header-tag2:custom.header-tag2"]
        tag_config_list = full_tag_config_list[1::]

        # tags = {custom.header-tag2: self.headers[header-tag2]}
        # tags = {custom.header-tag2: header-val2}
        tags = {(item.split(":")[1]).strip: (self.headers[item.split(":")[0]]).strip for item in tag_config_list}
        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)
