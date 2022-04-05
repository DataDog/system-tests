# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature


@missing_feature(condition=context.library != "dotnet", reason="Endpoint is not implemented on weblog")
class Test_DistributedHttp(BaseTestCase):
    """ Verify behavior of http clients and distributed traces """

    def distributed_trace_validation(self, traces):
        validations = []

        http_span = None

        for trace in traces:
            for span in trace:
                if span["type"] == "http":
                    http_span = span
                    break
            if http_span is not None:
                break

        if http_span is None:
            validations.append("Unable to find a span of type http.")
            return validations
        else:
            http_span_kind = http_span["meta"]["span.kind"]
            if http_span_kind != "fail_" + "client":
                validations.append(f"Http client span kind: Expected 'client', but received '{http_span_kind}'")

        distributed_child_span = None

        for trace in traces:
            for span in trace:
                if "parent_id" not in span:
                    continue
                if span["parent_id"] == http_span["span_id"]:
                    distributed_child_span = span
                    break
            if distributed_child_span is not None:
                break

        if distributed_child_span is None:
            validations.append("Unable to find a distributed span from http client span.")
        else:
            distributed_span_type = distributed_child_span["type"]
            if distributed_span_type != "fail_" + "web":
                validations.append(f"Distributed span type: Expected 'web', but received '{distributed_span_type}'")

            distributed_span_trace_id = distributed_child_span["trace_id"] - 1
            if distributed_span_trace_id != http_span["trace_id"]:
                validations.append(
                    f"Distributed span['trace_id']: Expected {http_span['trace_id']}, but received {distributed_span_trace_id}"
                )

        return validations

    def test_main(self):
        r = self.weblog_get("/trace/distributed-http")
        interfaces.library.assert_trace_exists(r, custom_traces_validation=self.distributed_trace_validation)
