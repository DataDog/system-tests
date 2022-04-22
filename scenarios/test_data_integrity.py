# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
from utils import BaseTestCase, interfaces, context, bug, irrelevant, rfc, released
from utils.tools import logger
from utils.cgroup_info import get_container_id


@rfc("https://github.com/DataDog/architecture/blob/master/rfcs/apm/integrations/submitting-traces-to-agent/rfc.md")
class Test_TraceHeaders(BaseTestCase):
    """All required headers are present in all traces submitted to the agent"""

    @bug(library="cpp", reason="https://github.com/DataDog/dd-opentracing-cpp/issues/194")
    def test_trace_header_container_tags(self):
        """Datadog-Container-ID header value is right in all traces submitted to the agent"""

        weblog_container_id = None

        USE_NEW_CGROUP_GETTER = context.weblog_variant in ("flask-poc",)

        if USE_NEW_CGROUP_GETTER:
            logger.debug(f"cgroup: using HTTP endpoint")
            r = self.weblog_get("/read_file", params={"file": "/proc/self/cgroup"})
            infos = r.text.split("\n")
        else:
            logger.debug(f"cgroup: using log file")
            with open("logs/docker/weblog/logs/weblog.cgroup", mode="r") as fp:
                infos = fp.readlines()

        logger.info(f"cgroup: file content is {infos}")

        weblog_container_id = get_container_id(infos)
        logger.info(f"cgroup: weblog container id is {weblog_container_id}")

        def validator(data):

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

            if weblog_container_id is not None:
                if "datadog-container-id" not in request_headers:
                    raise Exception(f"Datadog-Container-ID header is missing in request {data['log_filename']}")

                if request_headers["datadog-container-id"] != weblog_container_id:
                    raise Exception(
                        f"Expected Datadog-Container-ID header to be {weblog_container_id}, "
                        f"but got {request_headers['datadog-container-id']} "
                        f"in request {data['log_filename']}"
                    )

        interfaces.library.add_traces_validation(validator, is_success_on_expiry=True)
