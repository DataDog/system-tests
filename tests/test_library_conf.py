# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features
from utils._context.header_tag_vars import *


# basic / legacy tests, just tests user-agent can be received as a tag
@features.security_events_metadata
class Test_HeaderTags:
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags_basic(self):
        """Test that http.request.headers.user-agent is in all web spans"""

        for _, span in interfaces.library.get_root_spans():
            if span.get("type") == "web":
                assert "http.request.headers.user-agent" in span.get("meta", {})


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Short:
    """Validates that the short, header name only, format for specifying headers correctly tags spans"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_SHORT: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_SHORT: HEADER_VAL_BASIC}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Long:
    """Validates that input in `<header>:<tag_name>` format correctly tags spans"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_LONG: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_LONG: HEADER_VAL_BASIC}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Whitespace_Header:
    """Validates that leading/trailing whitespaces are trimmed on the header values given to DD_TRACE_HEADER_TAGS
    e.g, ' header ' in DD_TRACE_HEADER_TAGS=' header ' becomes 'header' and is expected to match req.header of 'header'
    """

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_WHITESPACE_HEADER: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_WHITESPACE_HEADER: HEADER_VAL_BASIC}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Whitespace_Tag:
    """Validates that leading/trailing whitespaces on the Input to DD_TRACE_HEADER_TAGS are
    trimmed on mapping parts, but whitespaces in between non-whitespace chars are left in-tact."""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_WHITESPACE_TAG: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_WHITESPACE_TAG: HEADER_VAL_BASIC}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Whitespace_Val_Short:
    """Validates that between-char whitespaces in header values are not removed,
    but leading/trailing whitespace is stripped, using short form input"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_WHITESPACE_VAL_SHORT: HEADER_VAL_WHITESPACE_VAL_SHORT}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_WHITESPACE_VAL_SHORT: HEADER_VAL_WHITESPACE_VAL_SHORT.strip()}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Whitespace_Val_Long:
    """Validates that between-char whitespaces in header values are not removed,
    but leading/trailing whitespace is stripped, using long form input"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_WHITESPACE_VAL_LONG: HEADER_VAL_WHITESPACE_VAL_LONG}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {TAG_WHITESPACE_VAL_LONG: HEADER_VAL_WHITESPACE_VAL_LONG.strip()}

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in tags:
                assert tag in span["meta"]


@scenarios.library_conf_custom_header_tags_invalid
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Colon_Leading:
    """Validates that Input to DD_TRACE_HEADER_TAGS with leading colon results in 0 additional span tags"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_COLON_LEADING: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        nottags = [
            HEADER_NAME_COLON_LEADING,
            TAG_COLON_LEADING,
            CONFIG_COLON_LEADING.split(":")[0],
            CONFIG_COLON_LEADING.split(":")[1],
        ]

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in nottags:
                assert tag not in span["meta"]


@scenarios.library_conf_custom_header_tags_invalid
@features.http_headers_as_tags_dd_trace_header_tags
class Test_HeaderTags_Colon_Trailing:
    """Validates that DD_TRACE_HEADER_TAGS input that contains a leading or trailing colon results in 0 additional span tags"""

    def setup_trace_header_tags(self):
        self.headers = {HEADER_NAME_COLON_TRAILING: HEADER_VAL_BASIC}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        nottags = [
            HEADER_NAME_COLON_TRAILING,
            TAG_COLON_TRAILING,
            CONFIG_COLON_TRAILING.split(":")[0],
            CONFIG_COLON_TRAILING.split(":")[1],
        ]

        for _, _, span in interfaces.library.get_spans(request=self.r):
            for tag in nottags:
                assert tag not in span["meta"]
