# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
import string
from utils import weblog, interfaces, context, bug, rfc, missing_feature, features
from utils.tools import logger
from utils.cgroup_info import get_container_id


@features.data_integrity
class Test_TraceUniqueness:
    """All trace ids are uniques"""

    def test_trace_ids(self):
        interfaces.library.assert_trace_id_uniqueness()


@rfc("https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/submitting-traces-to-agent/rfc.md")
@features.data_integrity
class Test_TraceHeaders:
    """All required headers are present in all traces submitted to the agent"""

    @missing_feature(library="cpp")
    @bug(context.library <= "golang@1.37.0")
    def test_traces_header_present(self):
        """Verify that headers described in RFC are present in traces submitted to the agent"""

        request_headers = [
            "datadog-meta-tracer-version",
            "datadog-meta-lang",
            "datadog-meta-lang-interpreter",
            "datadog-meta-lang-version",
            "x-datadog-trace-count",
        ]

        def check_condition(data):
            # if there is not trace, don't check anything
            return len(data["request"]["content"]) != 0

        interfaces.library.assert_headers_presence(
            r"/v[0-9]+\.[0-9]+/traces", request_headers=request_headers, check_condition=check_condition
        )

    def test_trace_header_diagnostic_check(self):
        """x-datadog-diagnostic-check header is present iif content is empty"""

        def validator(data):
            request_headers = {h[0].lower() for h in data["request"]["headers"]}
            if "x-datadog-diagnostic-check" in request_headers and len(data["request"]["content"]) != 0:
                raise ValueError("Tracer sent a dignostic request with traces in it")

        interfaces.library.add_traces_validation(validator=validator, success_by_default=True)

    def test_trace_header_count_match(self):
        """X-Datadog-Trace-Count header value is right in all traces submitted to the agent"""

        def validator(data):
            for header, value in data["request"]["headers"]:
                if header.lower() == "x-datadog-trace-count":
                    try:
                        trace_count = int(value)
                    except ValueError:
                        raise ValueError(f"'x-datadog-trace-count' request header is not an integer: {value}")

                    if trace_count != len(data["request"]["content"]):
                        raise ValueError("x-datadog-trace-count request header didn't match the number of traces")

        interfaces.library.add_traces_validation(validator=validator, success_by_default=True)

    def setup_trace_header_container_tags(self):
        self.r = weblog.get("/read_file", params={"file": "/proc/self/cgroup"})

    @bug(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/194")
    @missing_feature(
        context.library == "java" and "spring-boot" not in context.weblog_variant, reason="Missing endpoint"
    )
    @missing_feature(weblog_variant="spring-boot-3-native", reason="Missing endpoint")
    @missing_feature(
        context.library == "nodejs" and context.weblog_variant == "spring-boot-3-native", reason="Missing endpoint"
    )
    @missing_feature(context.library == "nodejs" and context.weblog_variant != "express4", reason="Missing endpoint")
    @missing_feature(context.library == "ruby" and context.weblog_variant != "rails70", reason="Missing endpoint")
    def test_trace_header_container_tags(self):
        """Datadog-Container-ID header value is right in all traces submitted to the agent"""

        assert self.r.status_code == 200
        infos = self.r.text.split("\n")

        logger.info(f"cgroup: file content is {infos}")

        weblog_container_id = get_container_id(infos)
        logger.info(f"cgroup: weblog container id is {weblog_container_id}")

        def validator(data):
            if _empty_request(data):
                # RFC states "Once container ID is stored locally in the tracer,
                # it must be sent to the Agent every time traces are sent."
                #
                # In case of PHP and Go, when requests with _empty content body_ are sent to /traces endpoint,
                # Datadog-Container-ID header is not present. However this is a non-issue, because there are anyway no
                # traces to which container tags could be attached.
                #
                # When the first /traces request with non-empty content body is sent, Datadog-Container-ID header is
                # present, like it would be expected.
                #
                # Thus ignore all /traces requests that have empty body, we should not require
                # Datadog-Container-ID header in this case.
                return

            request_headers = {h[0].lower(): h[1] for h in data["request"]["headers"]}

            if weblog_container_id is not None:
                if "datadog-container-id" not in request_headers:
                    raise ValueError(f"Datadog-Container-ID header is missing in request {data['log_filename']}")

                if request_headers["datadog-container-id"] != weblog_container_id:
                    raise ValueError(
                        f"Expected Datadog-Container-ID header to be {weblog_container_id}, "
                        f"but got {request_headers['datadog-container-id']} "
                        f"in request {data['log_filename']}"
                    )

        interfaces.library.add_traces_validation(validator, success_by_default=True)


@features.data_integrity
class Test_LibraryHeaders:
    """Misc test around headers sent by libraries"""

    def test_datadog_container_id(self):
        """Datadog-Container-ID header is not empty if present"""

        def validator(data):
            for header, value in data["request"]["headers"]:
                if header.lower() == "datadog-container-id":
                    assert value, "Datadog-Container-ID header is empty"

        interfaces.library.validate(validator, success_by_default=True)

    @missing_feature(library="nodejs", reason="not implemented yet")
    @missing_feature(library="ruby", reason="not implemented yet")
    @missing_feature(library="php", reason="not implemented yet")
    @missing_feature(library="cpp", reason="not implemented yet")
    @missing_feature(library="golang", reason="not implemented yet")
    def test_datadog_entity_id(self):
        """Datadog-Entity-ID header is present and respect the in-<digits> format"""

        def validator(data):
            if _empty_request(data):
                # Go sends an empty request content to /traces endpoint.
                # This is a non-issue, because there are no traces to which container tags could be attached.
                return
            if data["path"] in ("/info", "/v0.7/config"):
                # Those endpoints don't require Datadog-Entity-ID header, so skip them
                return
            request_headers = {h[0].lower(): h[1] for h in data["request"]["headers"]}
            if "datadog-entity-id" not in request_headers:
                raise ValueError(f"Datadog-Entity-ID header is missing in request {data['log_filename']}")
            val = request_headers["datadog-entity-id"]
            if val.startswith("in-"):
                assert val[3:].isdigit(), f"Datadog-Entity-ID header value {val} doesn't end with digits"
            elif val.startswith("cid-"):
                assert all(
                    c in string.hexdigits for c in val[4:]
                ), f"Datadog-Entity-ID header value {val} doesn't end with hex digits"
            else:
                raise ValueError(f"Datadog-Entity-ID header value {val} doesn't start with either 'in-' or 'cid-'")

        interfaces.library.validate(validator, success_by_default=True)


def _empty_request(data):
    return "content" not in data["request"] or not data["request"]["content"]
