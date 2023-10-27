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
                    if stats_point["EdgeTags"][0] == "direction:in":
                        consumer_stats_point = stats_point
                    elif stats_point["EdgeTags"][0] == "direction:out":
                        producer_stats_point = stats_point

                # consumers are a direct child of a producer span
                assert consumer_stats_point["ParentHash"] == producer_stats_point["Hash"]

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
            # Assert that the producer span is never a parent:
            child_span_of_producer_span = MQHelper.find_span_by_field(producer_span, trace, "span_id", "parent_id")
            assert child_span_of_producer_span == None

            # Check if the consumer span's ancestors contain the producer span at any point in the segment
            parent_span = ""
            starting_span = consumer_span
            while parent_span != None:
                parent_span = MQHelper.find_span_by_field(starting_span, trace, "parent_id", "span_id")
                if parent_span != None:
                    assert parent_span["span_id"] != producer_span["span_id"]

                starting_span = parent_span


class MQHelper:

    # Given a current span, look for the first span that matches a target field
    # Example: finding a current span's parent would be find_span_by_field(current_span, trace, "parent_id", "span_id")
    def find_span_by_field(current_span, trace, current_field="None", target_field="None"):
        for span in trace:
            if target_field in span.keys() and current_field in current_span.keys():
                if span[target_field] == current_span[current_field]:
                    return span
        return None
