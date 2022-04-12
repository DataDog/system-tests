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
