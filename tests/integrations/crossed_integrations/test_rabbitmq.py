from __future__ import annotations

import json

from utils.buddies import java_buddy, _Weblog as Weblog
from utils import interfaces, scenarios, weblog, missing_feature, features, logger


class _BaseRabbitMQ:
    """Test RabbitMQ compatibility with inputted datadog tracer"""

    BUDDY_TO_WEBLOG_QUEUE: str
    WEBLOG_TO_BUDDY_QUEUE: str
    WEBLOG_TO_BUDDY_EXCHANGE: str
    BUDDY_TO_WEBLOG_EXCHANGE: str
    BUDDY_TO_WEBLOG_ROUTING_KEY: str
    WEBLOG_TO_BUDDY_ROUTING_KEY: str
    buddy: Weblog
    buddy_interface: interfaces.LibraryInterfaceValidator

    @classmethod
    def get_span(cls, interface, span_kind, queue, exchange, operation) -> dict | None:
        logger.debug(f"Trying to find traces with span kind: {span_kind} and queue: {queue} in {interface}")

        for data, trace in interface.get_traces():
            for span in trace:
                if not span.get("meta"):
                    continue

                if span["meta"].get("span.kind") != span_kind:
                    continue

                operation_found = False
                for op in operation:
                    if op.lower() in span.get("resource").lower() or op.lower() in span.get("name").lower():
                        operation_found = True
                        break

                if not operation_found:
                    continue

                meta = span.get("meta")
                if (
                    queue.lower() not in span.get("resource").lower()
                    and exchange.lower() not in span.get("resource").lower()
                    and queue.lower() not in meta.get("rabbitmq.routing_key", "").lower()
                    # this is where we find the queue name in dotnet 👇
                    and queue.lower() not in meta.get("amqp.routing_key", "").lower()
                ):
                    continue

                logger.debug(f"span found in {data['log_filename']}:\n{json.dumps(span, indent=2)}")
                return span

        logger.debug("No span found")
        return None

    def setup_produce(self):
        """Send request A to weblog : this request will produce a RabbitMQ message
        send request B to library buddy, this request will consume RabbitMQ message
        """

        self.production_response = weblog.get(
            "/rabbitmq/produce",
            params={
                "queue": self.WEBLOG_TO_BUDDY_QUEUE,
                "exchange": self.WEBLOG_TO_BUDDY_EXCHANGE,
                "routing_key": self.WEBLOG_TO_BUDDY_ROUTING_KEY,
            },
            timeout=60,
        )
        self.consume_response = self.buddy.get(
            "/rabbitmq/consume",
            params={
                "queue": self.WEBLOG_TO_BUDDY_QUEUE,
                "exchange": self.WEBLOG_TO_BUDDY_EXCHANGE,
                "routing_key": self.WEBLOG_TO_BUDDY_ROUTING_KEY,
                "timeout": 60,
            },
            timeout=61,
        )

    def test_produce(self):
        """Check that a message produced to RabbitMQ is correctly ingested by a Datadog tracer"""

        assert self.production_response.status_code == 200, self.production_response.text
        assert self.consume_response.status_code == 200, self.consume_response.text

        # The weblog is the producer, the buddy is the consumer
        self.validate_rabbitmq_spans(
            producer_interface=interfaces.library,
            consumer_interface=self.buddy_interface,
            queue=self.WEBLOG_TO_BUDDY_QUEUE,
            exchange=self.WEBLOG_TO_BUDDY_EXCHANGE,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    def test_produce_trace_equality(self):
        """This test relies on the setup for produce, it currently cannot be run on its own"""
        producer_span = self.get_span(
            interfaces.library,
            span_kind="producer",
            queue=self.WEBLOG_TO_BUDDY_QUEUE,
            exchange=self.WEBLOG_TO_BUDDY_EXCHANGE,
            operation=["publish"],
        )
        consumer_span = self.get_span(
            self.buddy_interface,
            span_kind="consumer",
            queue=self.WEBLOG_TO_BUDDY_QUEUE,
            exchange=self.WEBLOG_TO_BUDDY_EXCHANGE,
            operation=["deliver", "receive"],
        )

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span is not None
        assert consumer_span is not None
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def setup_consume(self):
        """Send request A to library buddy : this request will produce a RabbitMQ message
        send request B to weblog, this request will consume RabbitMQ message

        request A: GET /library_buddy/produce_rabbitmq_message
        request B: GET /weblog/consume_rabbitmq_message
        """

        self.production_response = self.buddy.get(
            "/rabbitmq/produce",
            params={
                "queue": self.BUDDY_TO_WEBLOG_QUEUE,
                "exchange": self.BUDDY_TO_WEBLOG_EXCHANGE,
                "routing_key": self.BUDDY_TO_WEBLOG_ROUTING_KEY,
            },
            timeout=60,
        )
        self.consume_response = weblog.get(
            "/rabbitmq/consume",
            params={
                "queue": self.BUDDY_TO_WEBLOG_QUEUE,
                "exchange": self.WEBLOG_TO_BUDDY_EXCHANGE,
                "routing_key": self.BUDDY_TO_WEBLOG_ROUTING_KEY,
                "timeout": 60,
            },
            timeout=61,
        )

    def test_consume(self):
        """Check that a message by an app instrumented by a Datadog tracer is correctly ingested"""

        assert self.production_response.status_code == 200, self.production_response.text
        assert self.consume_response.status_code == 200, self.consume_response.text

        # The buddy is the producer, the weblog is the consumer
        self.validate_rabbitmq_spans(
            producer_interface=self.buddy_interface,
            consumer_interface=interfaces.library,
            queue=self.BUDDY_TO_WEBLOG_QUEUE,
            exchange=self.BUDDY_TO_WEBLOG_EXCHANGE,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    def test_consume_trace_equality(self):
        """This test relies on the setup for consume, it currently cannot be run on its own"""
        producer_span = self.get_span(
            self.buddy_interface,
            span_kind="producer",
            queue=self.BUDDY_TO_WEBLOG_QUEUE,
            exchange=self.BUDDY_TO_WEBLOG_EXCHANGE,
            operation=["publish"],
        )
        consumer_span = self.get_span(
            interfaces.library,
            span_kind="consumer",
            queue=self.BUDDY_TO_WEBLOG_QUEUE,
            exchange=self.BUDDY_TO_WEBLOG_EXCHANGE,
            operation=["deliver", "receive"],
        )

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span is not None
        assert consumer_span is not None
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def validate_rabbitmq_spans(self, producer_interface, consumer_interface, queue, exchange):
        """Validates production/consumption of RabbitMQ message.
        It works the same for both test_produce and test_consume
        """

        # Check that the producer did not create any consumer span
        assert (
            self.get_span(
                producer_interface,
                span_kind="consumer",
                queue=queue,
                exchange=exchange,
                operation=["deliver", "receive"],
            )
            is None
        )

        # Check that the consumer did not create any producer span
        assert (
            self.get_span(
                consumer_interface, span_kind="producer", queue=queue, exchange=exchange, operation=["publish"]
            )
            is None
        )

        producer_span = self.get_span(
            producer_interface, span_kind="producer", queue=queue, exchange=exchange, operation=["publish"]
        )
        consumer_span = self.get_span(
            consumer_interface, span_kind="consumer", queue=queue, exchange=exchange, operation=["deliver", "receive"]
        )
        # check that both consumer and producer spans exists
        assert producer_span is not None
        assert consumer_span is not None

        # Assert that the consumer span is not the root
        assert "parent_id" in consumer_span, "parent_id is missing in consumer span"

        # returns both span for any custom check
        return producer_span, consumer_span


@scenarios.crossed_tracing_libraries
@features.rabbitmq_span_creationcontext_propagation_with_dd_trace
class Test_RabbitMQ_Trace_Context_Propagation(_BaseRabbitMQ):
    buddy_interface = interfaces.java_buddy
    buddy = java_buddy
    WEBLOG_TO_BUDDY_QUEUE = "Test_RabbitMQ_Propagation_weblog_to_buddy"
    WEBLOG_TO_BUDDY_EXCHANGE = "Test_RabbitMQ_Propagation_weblog_to_buddy_exchange"
    WEBLOG_TO_BUDDY_ROUTING_KEY = "Test_RabbitMQ_Propagation_weblog_to_buddy_routing_key"
    BUDDY_TO_WEBLOG_QUEUE = "Test_RabbitMQ_Propagation_buddy_to_weblog"
    BUDDY_TO_WEBLOG_EXCHANGE = "Test_RabbitMQ_Propagation_buddy_to_weblog_exchange"
    BUDDY_TO_WEBLOG_ROUTING_KEY = "Test_RabbitMQ_Propagation_buddy_to_weblog_routing_key"
