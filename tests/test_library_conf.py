# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, weblog, interfaces, scenarios, features


# basic / legacy tests, just tests user-agent can be received as a tag
@coverage.basic
@features.security_events_metadata
class Test_HeaderTags:
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags_basic(self):
        """ Test that http.request.headers.user-agent is in all web spans """

        for _, span in interfaces.library.get_root_spans():
            if span.get("type") == "web":
                assert "http.request.headers.user-agent" in span.get("meta", {})


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
