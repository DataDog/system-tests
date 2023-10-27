# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, scenarios
from utils.tools import logger


@scenarios.integrations
class Test_MQKafka:
    def setup_apm_kafka_default_context_propagation(self):
        self.r = weblog.get("/dsm?integration=kafka")

    def setup_dsm_kafka_default_context_propagation(self):
        self.r = weblog.get("/dsm?integration=kafka")

    def test_dsm_kafka_default_context_propagation(self):
        for data in interfaces.agent.get_dsm_data():
            for stats_bucket in data["request"]["content"].get("Stats", {}):

                producer_stats_point = None
                consumer_stats_point = None

                for stats_point in stats_bucket.get("Stats", {}):
                    if stats_point["EdgeTags"][0] == 'direction:in':
                        consumer_stats_point = stats_point
                    elif stats_point["EdgeTags"][0] == 'direction:out':
                        producer_stats_point = stats_point

                assert consumer_stats_point['ParentHash'] == producer_stats_point['Hash']

    # kafka in dd-trace-py does not propagate span context for tracing purposes
    def test_apm_kafka_default_context_propagation(self):
        spans_payload = interfaces.library.get_spans(self.r)

        # get_spans returns several tuple items
        for items in spans_payload:
            # each iteration of spans_payload is a tuple
            data, trace, root_span = items
            producer_span = None
            consumer_span = None

            for span in trace:
                span_component = span["meta"]["component"]
                if "span.kind" in span["meta"].keys():
                    span_kind = span["meta"]["span.kind"]
                else:
                    span_kind = "none"

                if span_component == "kafka" and span_kind == "producer":
                    logger.debug("producer span found:", span)
                    producer_span = span
                elif span_component == "kafka" and span_kind == "consumer":
                    logger.debug("consumer span found:", span)
                    consumer_span = span

            assert producer_span is not None
            assert consumer_span is not None

            # consumer and producer spans have no direct parent/child relationship
            assert consumer_span["parent_id"] != producer_span["span_id"]
            assert producer_span["parent_id"] != consumer_span["span_id"]

            # Check for indirect relationships
            # Assert that the produce span is never a parent:
            is_producer_a_parent_span = False
            for span in trace:
                if "parent_id" in span.keys():
                    if span["parent_id"] == producer_span["trace_id"]:
                        is_producer_a_parent_span = True

            assert is_producer_a_parent_span == False
