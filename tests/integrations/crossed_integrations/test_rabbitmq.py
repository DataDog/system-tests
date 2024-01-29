from __future__ import annotations

import json

from tests.integrations.crossed_integrations.test_kafka import _python_buddy, _java_buddy
from utils import interfaces, scenarios, coverage, weblog, missing_feature, features
from utils.tools import logger


class _Test_RabbitMQ:
    """Test RabbitMQ compatibility with inputted datadog tracer"""

    BUDDY_TO_WEBLOG_QUEUE = None
    WEBLOG_TO_BUDDY_QUEUE = None
    buddy = None
    buddy_interface = None

    @classmethod
    def get_span(cls, interface, span_kind, queue, operation):
        logger.debug(f"Trying to find traces with span kind: {span_kind} and queue: {queue} in {interface}")

        for data, trace in interface.get_traces():
            for span in trace:
                if not span.get("meta"):
                    continue

                if span["meta"].get("span.kind") != span_kind:
                    continue

                if operation.lower() not in span.get("resource").lower():
                    continue

                if queue.lower() not in span.get("resource").lower():
                    continue

                logger.debug(f"span found in {data['log_filename']}:\n{json.dumps(span, indent=2)}")
                return span

        logger.debug("No span found")
        return None

    def setup_produce(self):
        """
        send request A to weblog : this request will produce a RabbitMQ message
        send request B to library buddy, this request will consume RabbitMQ message
        """

        self.production_response = weblog.get(
            "/rabbitmq/produce", params={"queue": self.WEBLOG_TO_BUDDY_QUEUE}, timeout=60
        )
        self.consume_response = self.buddy.get(
            "/rabbitmq/consume", params={"queue": self.WEBLOG_TO_BUDDY_QUEUE, "timeout": 60}, timeout=61
        )

    def test_produce(self):
        """Check that a message produced to RabbitMQ is correctly ingested by a Datadog tracer"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The weblog is the producer, the buddy is the consumer
        self.validate_rabbitmq_spans(
            producer_interface=interfaces.library,
            consumer_interface=self.buddy_interface,
            queue=self.WEBLOG_TO_BUDDY_QUEUE,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    def test_produce_trace_equality(self):
        """This test relies on the setup for produce, it currently cannot be run on its own"""
        producer_span = self.get_span(
            interfaces.library, span_kind="producer", queue=self.WEBLOG_TO_BUDDY_QUEUE, operation="basic.publish",
        )
        consumer_span = self.get_span(
            self.buddy_interface, span_kind="consumer", queue=self.WEBLOG_TO_BUDDY_QUEUE, operation="basic.deliver",
        )

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def setup_consume(self):
        """
        send request A to library buddy : this request will produce a RabbitMQ message
        send request B to weblog, this request will consume RabbitMQ message

        request A: GET /library_buddy/produce_rabbitmq_message
        request B: GET /weblog/consume_rabbitmq_message
        """

        self.production_response = self.buddy.get(
            "/rabbitmq/produce", params={"queue": self.BUDDY_TO_WEBLOG_QUEUE}, timeout=60
        )
        self.consume_response = weblog.get(
            "/rabbitmq/consume", params={"queue": self.BUDDY_TO_WEBLOG_QUEUE, "timeout": 60}, timeout=61
        )

    def test_consume(self):
        """Check that a message by an app instrumented by a Datadog tracer is correctly ingested"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The buddy is the producer, the weblog is the consumer
        self.validate_rabbitmq_spans(
            producer_interface=self.buddy_interface,
            consumer_interface=interfaces.library,
            queue=self.BUDDY_TO_WEBLOG_QUEUE,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    def test_consume_trace_equality(self):
        """This test relies on the setup for consume, it currently cannot be run on its own"""
        producer_span = self.get_span(
            self.buddy_interface, span_kind="producer", queue=self.BUDDY_TO_WEBLOG_QUEUE, operation="basic.publish",
        )
        consumer_span = self.get_span(
            interfaces.library, span_kind="consumer", queue=self.BUDDY_TO_WEBLOG_QUEUE, operation="basic.deliver",
        )

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def validate_rabbitmq_spans(self, producer_interface, consumer_interface, queue):
        """
        Validates production/consumption of RabbitMQ message.
        It works the same for both test_produce and test_consume
        """

        # Check that the producer did not created any consumer span
        assert self.get_span(producer_interface, span_kind="consumer", queue=queue, operation="basic.deliver") is None

        # Check that the consumer did not created any producer span
        assert self.get_span(consumer_interface, span_kind="producer", queue=queue, operation="basic.publish") is None

        producer_span = self.get_span(producer_interface, span_kind="producer", queue=queue, operation="basic.publish")
        consumer_span = self.get_span(consumer_interface, span_kind="consumer", queue=queue, operation="basic.deliver")
        # check that both consumer and producer spans exists
        assert producer_span is not None
        assert consumer_span is not None

        # Assert that the consumer span is not the root
        assert "parent_id" in consumer_span, "parent_id is missing in consumer span"

        # returns both span for any custom check
        return producer_span, consumer_span


@scenarios.crossed_tracing_libraries
@coverage.basic
@features.rabbitmq_span_creationcontext_propagation_with_dd_trace
class Test_RabbitMQ_Trace_Context_Propagation(_Test_RabbitMQ):
    buddy_interface = interfaces.java_buddy
    buddy = _java_buddy
    WEBLOG_TO_BUDDY_QUEUE = "Test_RabbitMQ_Propagation_weblog_to_buddy"
    BUDDY_TO_WEBLOG_QUEUE = "Test_RabbitMQ_Propagation_buddy_to_weblog"
