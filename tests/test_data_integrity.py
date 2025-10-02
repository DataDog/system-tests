# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""

import string
from utils import weblog, interfaces, context, bug, rfc, irrelevant, missing_feature, features, scenarios, logger
from utils.dd_constants import SamplingPriority
from utils.cgroup_info import get_container_id


@features.trace_data_integrity
class Test_TraceUniqueness:
    """All trace ids are uniques"""

    def test_trace_ids(self):
        interfaces.library.assert_trace_id_uniqueness()


@rfc("https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/submitting-traces-to-agent/rfc.md")
@features.trace_data_integrity
class Test_TraceHeaders:
    """All required headers are present in all traces submitted to the agent"""

    @missing_feature(library="cpp_nginx")
    @missing_feature(library="cpp_httpd")
    @bug(context.library <= "golang@1.37.0", reason="APMRP-360")
    def test_traces_header_present(self):
        """Verify that headers described in RFC are present in traces submitted to the agent"""

        request_headers = (
            "datadog-meta-tracer-version",
            "datadog-meta-lang",
            "datadog-meta-lang-interpreter",
            "datadog-meta-lang-version",
            "x-datadog-trace-count",
        )

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
                    except ValueError as e:
                        raise ValueError(f"'x-datadog-trace-count' request header is not an integer: {value}") from e

                    if trace_count != len(data["request"]["content"]):
                        raise ValueError("x-datadog-trace-count request header didn't match the number of traces")

        interfaces.library.add_traces_validation(validator=validator, success_by_default=True)

    def setup_trace_header_container_tags(self):
        self.r = weblog.get("/read_file", params={"file": "/proc/self/cgroup"})

    @missing_feature(
        context.library == "java" and "spring-boot" not in context.weblog_variant, reason="Missing endpoint"
    )
    @missing_feature(
        context.library == "java" and context.weblog_variant == "spring-boot-3-native", reason="Missing endpoint"
    )
    @missing_feature(
        context.library == "nodejs" and context.weblog_variant not in ["express4", "express5"],
        reason="Missing endpoint",
    )
    @missing_feature(context.library == "ruby" and context.weblog_variant != "rails70", reason="Missing endpoint")
    @missing_feature(context.library == "cpp_httpd", reason="Missing endpoint")
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


@features.trace_data_integrity
class Test_LibraryHeaders:
    """Misc test around headers sent by libraries"""

    def test_datadog_container_id(self):
        """Datadog-Container-ID header is not empty if present"""

        def validator(data):
            for header, value in data["request"]["headers"]:
                if header.lower() == "datadog-container-id":
                    assert value, "Datadog-Container-ID header is empty"

        interfaces.library.validate(validator, success_by_default=True)

    @missing_feature(context.library < "nodejs@5.47.0", reason="not implemented yet")
    @missing_feature(library="ruby", reason="not implemented yet")
    @missing_feature(library="php", reason="not implemented yet")
    @missing_feature(library="cpp_nginx", reason="not implemented yet")
    @missing_feature(library="cpp_httpd")
    @irrelevant(library="golang", reason="implemented but not testable")
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
            elif val.startswith("ci-"):
                assert all(
                    c in string.hexdigits for c in val[3:]
                ), f"Datadog-Entity-ID header value {val} doesn't end with hex digits"
            # The cid prefix is deprecated and will be removed in a future version of the agent
            elif val.startswith("cid-"):
                assert all(
                    c in string.hexdigits for c in val[4:]
                ), f"Datadog-Entity-ID header value {val} doesn't end with hex digits"
            else:
                raise ValueError(
                    f"Datadog-Entity-ID header value {val} doesn't start with either 'in-', 'ci-' or 'cid-'"
                )

        interfaces.library.validate(validator, success_by_default=True)

    @missing_feature(library="cpp_nginx", reason="not implemented yet")
    @missing_feature(library="cpp_httpd", reason="not implemented yet")
    @missing_feature(library="dotnet", reason="not implemented yet")
    @missing_feature(library="java", reason="not implemented yet")
    @missing_feature(context.library < "nodejs@5.47.0", reason="not implemented yet")
    @missing_feature(library="php", reason="not implemented yet")
    @missing_feature(library="ruby", reason="not implemented yet")
    @missing_feature(context.library < "golang@1.73.0-dev", reason="Implemented in v1.72.0")
    def test_datadog_external_env(self):
        """Datadog-External-Env header if present is in the {prefix}-{value},... format"""

        def validator(data):
            # Only test this when the path ens in /traces
            if not data["path"].endswith("/traces"):
                return
            if _empty_request(data):
                # Go sends an empty request content to /traces endpoint.
                # This is a non-issue, because there are no traces to which container tags could be attached.
                return
            request_headers = {h[0].lower(): h[1] for h in data["request"]["headers"]}
            if "datadog-external-env" not in request_headers:
                raise ValueError(f"Datadog-External-ID header is missing in request {data['log_filename']}")
            value = request_headers["datadog-external-env"]
            items = value.split(",")
            for item in items:
                assert (
                    item[2] == "-"
                ), f"Datadog-External-Env item {item} is not using in the format {{prefix}}-{{value}}"

        interfaces.library.validate(validator, success_by_default=True)

    @missing_feature(library="cpp_nginx", reason="Trace are not reported")
    @missing_feature(library="cpp_httpd")
    # we are not using dev agent, so activate this to see if it fails
    # @flaky(context.agent_version > "7.62.2", reason="APMSP-1791")
    def test_headers(self):
        """All required headers are present in all requests sent by the agent"""
        interfaces.library.assert_response_header(
            path_filters=interfaces.library.trace_paths,
            header_name_pattern="content-type",
            header_value_pattern="application/json",
        )

    def test_traces_coherence(self):
        """Agent does not like incoherent data. Check that no incoherent data are coming from the tracer"""

        for data, trace in interfaces.library.get_traces():
            assert data["response"]["status_code"] == 200
            trace_id = trace[0]["trace_id"]
            assert isinstance(trace_id, int)
            assert trace_id > 0
            for span in trace:
                assert span["trace_id"] == trace_id


@features.agent_data_integrity
@scenarios.sampling
@scenarios.default
class Test_Agent:
    def test_agent_do_not_drop_traces(self):
        """Agent does not drop traces"""

        # get list of trace ids reported by the agent
        trace_ids_reported_by_agent = set()
        for _, span in interfaces.agent.get_spans():
            trace_ids_reported_by_agent.add(int(span["traceID"]))

        def get_span_with_sampling_data(trace):
            # The root span is not necessarily the span wherein the sampling priority can be found.
            # If present, the root will take precedence, and otherwise the first span with the
            # sampling priority tag will be returned. This isthe same logic found on the trace-agent.
            span_with_sampling_data = None
            for span in trace:
                if span.get("metrics", {}).get("_sampling_priority_v1", None) is not None:
                    if span.get("parent_id") in (0, None):
                        return span
                    elif span_with_sampling_data is None:
                        span_with_sampling_data = span

            return span_with_sampling_data

        all_traces_are_reported = True
        trace_ids_reported_by_tracer = set()
        # check that all traces reported by the tracer are also reported by the agent
        for data, trace in interfaces.library.get_traces():
            span = get_span_with_sampling_data(trace)
            if not span:
                continue

            metrics = span["metrics"]
            sampling_priority = metrics.get("_sampling_priority_v1")
            if sampling_priority in (SamplingPriority.AUTO_KEEP, SamplingPriority.USER_KEEP):
                trace_ids_reported_by_tracer.add(span["trace_id"])
                if span["trace_id"] not in trace_ids_reported_by_agent:
                    logger.error(f"Trace {span['trace_id']} has not been reported ({data['log_filename']})")
                    all_traces_are_reported = False
                else:
                    logger.debug(f"Trace {span['trace_id']} has been reported ({data['log_filename']})")

        if not all_traces_are_reported:
            logger.info(f"Tracer reported {len(trace_ids_reported_by_tracer)} traces")
            logger.info(f"Agent reported {len(trace_ids_reported_by_agent)} traces")
            raise ValueError("Some traces have not been reported by the agent. See logs for more details")


def _empty_request(data):
    return "content" not in data["request"] or not data["request"]["content"]
