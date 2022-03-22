# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils.interfaces._core import BaseValidation
from utils import context


class _TraceHeadersContainerTags(BaseValidation):
    """Verify that valid container tags described in
    https://github.com/DataDog/architecture/blob/master/rfcs/apm/agent/containers-tagging/rfc.md
    are submitted to the agent"""

    is_success_on_expiry = True
    path_filters = r"/v0\.[1-9]+/traces"  # Should be implemented independently from the endpoint version

    def check(self, data):
        if "content" not in data["request"] or not data["request"]["content"]:
            # RFC states "Once container ID is stored locally in the tracer, it must be sent to the Agent every time
            # traces are sent."
            #
            # In case of PHP and Go, when requests with _empty content body_ are sent to /traces endpoint,
            # Datadog-Container-ID header is not present. However this is a non-issue, because there are anyway no
            # traces to which container tags could be attached.
            #
            # When the first /traces request with non-empty content body is sent, Datadog-Container-ID header is
            # present, like it would be expected.
            #
            # Thus ignore all /traces requests that have empty body, we should not require Datadog-Container-ID header
            # in this case.
            return

        request_headers = {h[0].lower(): h[1] for h in data["request"]["headers"]}

        expected_value = context.get_weblog_container_id()

        if expected_value is not None:
            if "datadog-container-id" not in request_headers:
                self.set_failure(f"Datadog-Container-ID header is missing in request {data['log_filename']}")
                return

            if request_headers["datadog-container-id"] != expected_value:
                self.set_failure(
                    f"Expected Datadog-Container-ID header to be {expected_value}, "
                    f"but got {request_headers['datadog-container-id']} "
                    f"in request {data['log_filename']}"
                )


class _TraceHeadersContainerTagsCpp(BaseValidation):
    """Verify that C++ implementation doesn't submit valid container tags described in
    https://github.com/DataDog/architecture/blob/master/rfcs/apm/agent/containers-tagging/rfc.md"""

    is_success_on_expiry = True
    path_filters = r"/v0\.[1-9]+/traces"  # Should be implemented independently from the endpoint version

    def check(self, data):
        if "content" not in data["request"] or not data["request"]["content"]:
            # Ignore all /traces requests that have empty body, we should not require Datadog-Container-ID header
            # in this case.
            return

        request_headers = {h[0].lower(): h[1] for h in data["request"]["headers"]}

        if "datadog-container-id" in request_headers:
            self.set_failure(
                f"Datadog-Container-ID header is present in request {data['log_filename']}. "
                f"Please remove special Datadog-Container-ID test case for C++."
            )
            return


class _TraceHeadersPresent(BaseValidation):
    """Verify that headers described in
    https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/submitting-traces-to-agent/rfc.md
    are present in traces submitted to the agent"""

    is_success_on_expiry = True
    path_filters = r"/v0\.[1-9]+/traces"  # Should be implemented independently from the endpoint version
    required_headers = {
        "datadog-meta-tracer-version",
        "datadog-meta-lang",
        "datadog-meta-lang-interpreter",
        "datadog-meta-lang-version",
        "x-datadog-trace-count",
    }

    def check(self, data):
        request_headers = {h[0].lower() for h in data["request"]["headers"]}
        missing_headers = self.required_headers - request_headers
        if missing_headers:
            self.set_failure(f"Headers {missing_headers} are missing in request {data['log_filename']}")


class _TraceHeadersPresentPhp(_TraceHeadersPresent):
    """Special test for the php tracer to filter trace submissions containing
    x-datadog-diagnostic-check but still ensure other requests headers are correct"""

    def check(self, data):
        request_headers = {h[0].lower() for h in data["request"]["headers"]}
        if context.library == "php" and "x-datadog-diagnostic-check" in request_headers:
            if len(data["request"]["content"]) != 0:
                self.set_failure("Php tracer sent a dignostic request with traces in it")
            return

        return super().check(data)


class _TraceHeadersCount(BaseValidation):
    """Verify that the X-Datadog-Trace-Count header value is right"""

    is_success_on_expiry = True
    path_filters = r"/v0\.[1-9]+/traces"  # Should be independent from the endpoint version
    count_header = "x-datadog-trace-count"

    def check(self, data):
        trace_count = next((h[1] for h in data["request"]["headers"] if h[0].lower() == self.count_header), None)
        if trace_count is None:
            return
        try:
            trace_count = int(trace_count)
            if trace_count != len(data["request"]["content"]):
                self.set_failure(
                    f"{self.count_header} value in request {data['log_filename']} didn't match the number of traces"
                )
        except ValueError:
            self.set_failure(f"{self.count_header} value in request {data['log_filename']} wasn't an integer")
