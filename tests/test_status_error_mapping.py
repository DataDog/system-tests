# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature, scenarios
from utils.tools import logger
from utils import (
    bug,
    context,
    coverage,
    interfaces,
    irrelevant,
    rfc,
    weblog,
    missing_feature,
)

# TODO: figure out how to add in the environment variable to only effec this test.
### CLIENT SPANS ###
# 400-413 should be an error
# 414-499 should not be an error
# depending on the language and framework, some status codes will return an error so we need to test within its limits
# for example, trying 455 in Java, spring-boot will return 500 as 455 is not an appropiate status code.

###  SERVER SPANS ###
# 500-510 should be an error
# 511-599 should not be an error


@rfc(
    "https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/status-error-mapping/rfc.md"
)
class Test_Error_Status_Mapping:
    """ Verify behavior of Error Status Mapping for Client and Server"""

    def setup_should_be_error_server_span(self):
        self.r_501 = weblog.get("/status", params={"code": "501"})

    def test_should_be_error_server_span(self):
        for data, trace, span in interfaces.library.get_spans():
            if (
                "span.kind" not in span["meta"].keys()
                or "http.status_code" not in span["meta"].keys()
            ):
                continue
            if span["meta"]["span.kind"] == "server":
                if span["meta"]["http.status_code"] == "501":
                    logger.debug("this is for should be error span: %s \n", span)
                    assert span["error"] == 1, "this span should be marked as an error"
                    return
        assert (
            False
        ), "there were 0 spans with the tags span.kind and http.status_code needed to test the custom error tag functionality"

    def setup_should_not_be_error_server_span(self):
        self.r_511 = weblog.get("/status", params={"code": "511"})

    def test_should_not_be_error_server_span(self):
        for data, trace, span in interfaces.library.get_spans():
            if (
                "span.kind" not in span["meta"].keys()
                or "http.status_code" not in span["meta"].keys()
            ):
                continue
            if span["meta"]["span.kind"] == "server":
                if span["meta"]["http.status_code"] == "511":
                    # logger.debug("this is for should NOT be error span: %s \n", span)
                    assert (
                        "error" not in span or span["error"] == 0
                    ), "this span should not be an error"
                    return
        assert (
            False
        ), "there were 0 spans with the tags span.kind and http.status_code needed to test the custom error tag functionality"

    def setup_should_be_error_client_span(self):
        self.r_413 = weblog.get(
            "/make_distant_call", params={"url": "http://weblog:7777/status?code=413"}
        )

    def test_should_be_error_client_span(self):
        for data, trace, span in interfaces.library.get_spans():
            if (
                "span.kind" not in span["meta"].keys()
                or "http.status_code" not in span["meta"].keys()
            ):
                continue
            if span["meta"]["span.kind"] == "client":
                if span["meta"]["http.status_code"] == "413":
                    # logger.debug("this is for should be error span: %s \n", span)
                    assert span["error"] == 1, "this span should be marked as an error"
                    return
        assert (
            False
        ), "there were 0 spans with the tags span.kind and http.status_code needed to test the custom error tag functionality"

    def setup_should_not_be_error_client_span(self):
        self.r_416 = weblog.get(
            "/make_distant_call", params={"url": "http://weblog:7777/status?code=416"}
        )

    def test_should_not_be_error_client_span(self):
        for data, trace, span in interfaces.library.get_spans():
            if (
                "span.kind" not in span["meta"].keys()
                or "http.status_code" not in span["meta"].keys()
            ):
                continue
            if span["meta"]["span.kind"] == "client":
                if span["meta"]["http.status_code"] == "416":
                    # logger.debug("this is for should NOT be error span: %s \n", span)
                    assert (
                        "error" not in span or span["error"] == 0
                    ), "this span should not be an error"
                    return
        assert (
            False
        ), "there were 0 spans with the tags span.kind and http.status_code needed to test the custom error tag functionality"
