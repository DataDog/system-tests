# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import re
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
@released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="0.74.0", python="?", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_short
class Test_HeaderTagsShortFormat:
    """Validates that the short, header name only, format for specifying headers correctly tags spans"""

    def setup_trace_header_tags(self):
        self.headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_headers_short.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        tag_config_list = full_tag_config_list[1::]

        tags = {"http.request.headers." + tag: self.headers[tag] for tag in tag_config_list}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="?", python="1.2.1", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_long
class Test_HeaderTagsLongFormat:
    """Validates that the short, header : tag name, format for specifying headers correctly tags spans"""

    def setup_trace_header_tags(self):
        self.headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_headers_long.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        tag_config_list = full_tag_config_list[1::]

        tags = {item.split(":")[1]: self.headers[item.split(":")[0]] for item in tag_config_list}
        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="?", python="1.2.1", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_whitespacing_headers
class Test_HeaderTagsWhitespacing_Headers:
    """Validates that leading/trailing whitespaces are trimmed on the header values given to DD_TRACE_HEADER_TAGS
    e.g, ' header ' in DD_TRACE_HEADER_TAGS=' header ' becomes 'header' and is expected to match req.header of 'header' """

    def setup_trace_header_tags(self):
        # " header-tag1 ", "h e a d e r - t a g 2"
        self.headers = {"header-tag1": "header-val1"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_headers_whitespacing_headers.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        tag_config_list = full_tag_config_list[1::]

        tags = {}
        for tag in tag_config_list:
            tag = tag.strip()
            tags["http.request.headers." + tag] = re.sub("[^a-zA-Z0-9 -]", "_", self.headers[tag])

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="?", python="1.2.1", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_whitespacing_tags
class Test_HeaderTagsWhitespacing_Tags:
    """Validates that leading/trailing whitespaces are trimmed on mapping parts, but whitespaces
    in between non-whitespace chars are left in-tact."""

    def setup_trace_header_tags(self):
        self.headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_headers_whitespacing_tags.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        tag_config_list = full_tag_config_list[1::]

        tags = {}

        for item in tag_config_list:
            tag = (item.split(":")[1]).strip()
            val = self.headers[item.split(":")[0]].strip()
            tags[tag] = val
        
        # tags = {(item.split(":")[1]).strip(): (self.headers[item.split(":")[0]]).strip() for item in tag_config_list}
        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="0.74.0", python="?", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_whitespacing_vals
class Test_HeaderTagsWhitespacing_Vals:
    """ Validates that whitespaces in header values are not removed in the span tag value """

    def setup_trace_header_tags(self):
        self.headers = {"header-tag1": "header-val1 ", "header-tag2": "h e a d e r - v a l 2"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_headers_whitespacing_vals.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        tag_config_list = full_tag_config_list[1::]

        tags = {}
        for tag in tag_config_list:
            val = self.headers[tag].strip()
            tags["http.request.headers." + tag] = val

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

# @irrelevant(library="cpp")
# @released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="0.74.0", python="?", ruby="?")
# @coverage.basic
# @scenarios.library_conf_custom_headers_colon_multi
# class Test_HeaderTagsColon_Multi:
#     """ Validates that input to DD_TRACE_HEADER_TAGS will be split on the last colon, e.g,
#     in DD_TRACE_HEADER_TAGS='first:second:third', 'first:second' is considered the header, and 'third' the tag."""

#     def setup_trace_header_tags(self):
#         self.headers = {"first": "header-val1", "second": "header-val2", "third": "header-val3", "first:second": "special"}
#         self.r = weblog.get("/waf", headers=self.headers)

#     def test_trace_header_tags(self):
#         tag_conf = scenarios.library_conf_custom_headers_colon_multi.weblog_container.environment["DD_TRACE_HEADER_TAGS"]
        
#         full_tag_config_list = tag_conf.split(",")
#         # skip the first item, as this required to make the tests work on some platforms
#         tag_config_list = full_tag_config_list[1::]

#         tags = {item.rsplit(":", 1)[1]: self.headers[item.rsplit(":", 1)[0]] for item in tag_config_list}
#         interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

@irrelevant(library="cpp")
@released(dotnet="2.1.0", golang="?", java="0.102.0", nodejs="?", php="0.74.0", python="?", ruby="?")
@coverage.basic
@scenarios.library_conf_custom_headers_colon_edge
class Test_HeaderTagsColon_Edge:
    """ Validates that input with leading & trailing colons is still considered a tag mapping input """

    def setup_trace_header_tags(self):
        self.headers = {"header-tag1": "header-val1", "header-tag2": "header-val2"}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tag_conf = scenarios.library_conf_custom_headers_colon_edge.weblog_container.environment["DD_TRACE_HEADER_TAGS"]

        full_tag_config_list = tag_conf.split(",")
        # skip the first item, as this required to make the tests work on some platforms
        tag_config_list = full_tag_config_list[1::]

        nottags = []
        for item in tag_config_list:
            nottags.append("http.request.headers." + item)
            splitItem = item.split(":")
            nottags.append(splitItem[0])
            nottags.append(splitItem[1])

        interfaces.library.add_not_span_tag_validation(request=self.r, nottags=nottags)