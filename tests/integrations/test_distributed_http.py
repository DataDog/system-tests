# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature

# ./build.sh ${language} --weblog-variant ${weblogvariant}
# ./run.sh /tests/integrations/test_distributed_http.py::Test_DistributedHttp::test_main
@missing_feature(library="java", reason="Endpoint is not implemented on weblog")
@missing_feature(library="nodejs", reason="Endpoint is not implemented on weblog")
@missing_feature(library="php", reason="Endpoint is not implemented on weblog")
@missing_feature(library="ruby", reason="Endpoint is not implemented on weblog")
@missing_feature(library="cpp", reason="Endpoint is not implemented on weblog")
class Test_DistributedHttp(BaseTestCase):
    """ Verify behavior of http clients and distributed traces """

    def distributed_trace_validation(self, spans):
        validations = []

        http_span = None

        for span in spans:
            if "type" in span and span["type"] == "http":
                http_span = span
                break

        if http_span is None:
            validations.append("Unable to find a span of type http.")
            return validations

        distributed_child_span = None

        for span in spans:
            if "parent_id" not in span:
                continue
            if span["parent_id"] == http_span["span_id"]:
                distributed_child_span = span
                break

        if distributed_child_span is None:
            validations.append("Unable to find a distributed span from http client span.")
        else:
            distributed_span_type = distributed_child_span["type"]
            if distributed_span_type != "web":
                validations.append(f"Distributed span type: Expected 'web', but received '{distributed_span_type}'")

            distributed_span_trace_id = distributed_child_span["trace_id"]
            if distributed_span_trace_id != http_span["trace_id"]:
                validations.append(
                    f"Distributed span trace ID: Expected {http_span['trace_id']}, but received {distributed_span_trace_id}"
                )

        return validations

    def test_main(self):
        r = self.weblog_get("/distributed-http")
        interfaces.library.assert_against_distributed_trace(r, validator=self.distributed_trace_validation)
