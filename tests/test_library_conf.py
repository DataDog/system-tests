# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, weblog, interfaces, scenarios
from utils._context.header_tag_vars import Header_Value, Config, Tag, Header_Name, Header_Value

# basic / legacy tests, just tests user-agent can be received as a tag
@coverage.basic
class Test_HeaderTags:
    """DD_TRACE_HEADER_TAGS env var support"""

    def test_trace_header_tags_basic(self):
        """ Test that http.request.headers.user-agent is in all web spans """

        for _, span in interfaces.library.get_root_spans():
            if span.get("type") == "web":
                assert "http.request.headers.user-agent" in span.get("meta", {})

@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTags_Short:
    """Validates that the short, header name only, format for specifying headers correctly tags spans"""
    def setup_trace_header_tags(self):
        self.name = self.__class__.__name__ #Test_HeaderTags_Short
        self.headers = {Header_Name(self.name): Header_Value(self.name)}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {Tag(self.name): Header_Value(self.name)}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTags_Long:
    """Validates that input in `<header>:<tag_name>` format correctly tags spans"""

    def setup_trace_header_tags(self):
        self.name = self.__class__.__name__ #Test_HeaderTags_Long
        self.headers =  {Header_Name(self.name): Header_Value(self.name)}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {Tag(self.name): Header_Value(self.name)}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTags_Whitespace_Header:
    """Validates that leading/trailing whitespaces are trimmed on the header values given to DD_TRACE_HEADER_TAGS
    e.g, ' header ' in DD_TRACE_HEADER_TAGS=' header ' becomes 'header' and is expected to match req.header of 'header' """

    def setup_trace_header_tags(self):
        self.name = self.__class__.__name__ #Test_HeaderTags_Whitespace_Header
        self.headers =  {Header_Name(self.name): Header_Value(self.name)}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {Tag(self.name).strip(): Header_Value(self.name)}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTags_Whitespace_Tag:
    """Validates that leading/trailing whitespaces on the Input to DD_TRACE_HEADER_TAGS are 
    trimmed on mapping parts, but whitespaces in between non-whitespace chars are left in-tact."""

    def setup_trace_header_tags(self):
        self.name = self.__class__.__name__ #Test_HeaderTags_Whitespace_Tag
        self.headers =  {Header_Name(self.name): Header_Value(self.name)}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {Tag(self.name).strip(): Header_Value(self.name)}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTags_Whitespace_Val_Short:
    """Validates that between-char whitespaces in header values are not removed,
    but leading/trailing whitespace is stripped, using short form input"""

    def setup_trace_header_tags(self):
        self.name = self.__class__.__name__ #Test_HeaderTags_Whitespace_Val_Short
        self.headers =  {Header_Name(self.name): Header_Value(self.name)}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {Tag(self.name): Header_Value(self.name).strip()}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)

@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTags_Whitespace_Val_Long:
    """Validates that between-char whitespaces in header values are not removed,
    but leading/trailing whitespace is stripped, using long form input"""

    def setup_trace_header_tags(self):
        self.name = self.__class__.__name__ #Test_HeaderTags_Whitespace_Val_Long
        self.headers =  {Header_Name(self.name): Header_Value(self.name)}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        tags = {Tag(self.name): Header_Value(self.name).strip()}

        interfaces.library.add_span_tag_validation(request=self.r, tags=tags)


@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTags_Colon_Leading:
    """ Validates that Input to DD_TRACE_HEADER_TAGS with leading colon results in 0 additional span tags """

    def setup_trace_header_tags(self):
        self.name = self.__class__.__name__ #Test_HeaderTags_Colon_Leading
        self.headers =  {Header_Name(self.name): Header_Value(self.name)}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        nottags = [Header_Name(self.name), Tag(self.name), Config(self.name).split(":")[0], Config(self.name).split(":")[1]]

        interfaces.library.add_not_span_tag_validation(request=self.r, nottags=nottags)

@coverage.basic
@scenarios.library_conf_custom_header_tags
class Test_HeaderTags_Colon_Trailing:
    """ Validates that Input to DD_TRACE_HEADER_TAGS with trailing colon results in 0 additional span tags """

    def setup_trace_header_tags(self):
        self.name = self.__class__.__name__ #Test_HeaderTags_Colon_Trailing
        self.headers =  {Header_Name(self.name): Header_Value(self.name)}
        self.r = weblog.get("/waf", headers=self.headers)

    def test_trace_header_tags(self):
        nottags = [Header_Name(self.name), Tag(self.name), Config(self.name).split(":")[0], Config(self.name).split(":")[1]]

        interfaces.library.add_not_span_tag_validation(request=self.r, nottags=nottags)