# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, scenarios
from utils.tools import logger


@scenarios.integrations
class Test_MQKafka:
    def setup_apm_kafka_default_context_propagation(self):
        self.r = weblog.get("/dsm?integration=kafka")

    def setup_apm_kafka_distributed_context_propagation(self):
        self.producer_r = weblog.get("/apm?integration=kafka&applicationtype=producer")
        self.consumer_r = weblog.get("/apm?integration=kafka&applicationtype=consumer")

    # Tests against the DSM endpoint where producer and consumer calls are made one within the same endpoint
    def test_apm_kafka_default_context_propagation(self):
        spans_payload = interfaces.library.get_spans(self.r)

        # get_spans returns several tuple items
        for items in spans_payload:
            # each iteration of spans_payload is a tuple
            data, trace, root_span = items
            producer_span, consumer_span = MQHelper.find_producer_consumer_spans(trace)
            assert producer_span is not None
            assert consumer_span is not None

            # consumer and producer spans have a direct parent/child relationship
            assert consumer_span["parent_id"] == producer_span["span_id"]
            assert producer_span["parent_id"] == consumer_span["span_id"]

    # Assert the behavior for distributed apps
    def test_apm_kafka_distributed_context_propagation(self):
        producer_lang = ["python"]
        consumer_lang = ["python"]

        for lang in producer_lang:
            for lang in consumer_lang:
                producer_span_from_producer_endpoint = None
                consumer_span_from_consumer_endpoint = None

                producer_endpoint_spans_payload = interfaces.library.get_spans(self.producer_r)

                # get_spans returns several tuple items
                for items in producer_endpoint_spans_payload:
                    data, trace, root_span = items

                    # The producer endpoint should not generate any consume spans
                    producer_span, consumer_span = MQHelper.find_producer_consumer_spans(trace)
                    assert producer_span is not None
                    assert consumer_span is None
                    producer_span_from_producer_endpoint = producer_span

                consumer_endpoint_spans_payload = interfaces.library.get_spans(self.consumer_r)
                for items in consumer_endpoint_spans_payload:
                    data, trace, root_span = items

                    producer_span, consumer_span = MQHelper.find_producer_consumer_spans(trace)
                    assert producer_span is None
                    assert consumer_span is not None
                    consumer_span_from_consumer_endpoint = consumer_span

            # consumer and producer spans have a direct parent/child relationship
            assert consumer_span_from_consumer_endpoint["parent_id"] == producer_endpoint_spans_payload["span_id"]
            assert producer_endpoint_spans_payload["parent_id"] == consumer_span_from_consumer_endpoint["span_id"]


class MQHelper:

    # Given a trace payload, find the producer and consumer spans
    def find_producer_consumer_spans(trace):
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

        return producer_span, consumer_span
