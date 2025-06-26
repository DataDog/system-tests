from __future__ import annotations

import json

from utils import interfaces, scenarios, weblog, missing_feature, features, logger, context
from utils.buddies import java_buddy, _Weblog as Weblog


class _BaseKafka:
    """Test kafka compatibility with inputted datadog tracer"""

    buddy: Weblog
    WEBLOG_TO_BUDDY_TOPIC: str
    BUDDY_TO_WEBLOG_TOPIC: str
    buddy_interface: interfaces.LibraryInterfaceValidator
    tracer_to_integration: dict

    @classmethod
    def get_span(cls, interface, span_kind, topic) -> dict | None:
        logger.debug(f"Trying to find traces with span kind: {span_kind} and topic: {topic} in {interface}")

        for data, trace in interface.get_traces():
            for span in trace:
                if not span.get("meta"):
                    continue

                if span_kind != span["meta"].get("span.kind"):
                    continue

                if topic != cls.get_topic(span):
                    continue

                # we may have multiple integrations for the same tracer, so we need to check the component
                if (
                    cls.tracer_to_integration.get(context.library.name, None) is not None
                    and "buddy" not in interface.name
                ):
                    if cls.tracer_to_integration.get(context.library.name, None) != span["meta"].get("component"):
                        continue

                logger.debug(f"span found in {data['log_filename']}:\n{json.dumps(span, indent=2)}")
                return span

        logger.debug("No span found")
        return None

    @staticmethod
    def get_topic(span) -> str | None:
        """Extracts the topic from a span by trying various fields"""
        topic = span["meta"].get("kafka.topic")  # this is in python
        if topic is None:
            if "Topic" in span["resource"]:
                # in go and java, the topic is the last "word" of the resource name
                topic = span["resource"].split(" ")[-1]

        if topic is None:
            logger.error(f"could not extract topic from this span:\n{span}")
        return topic

    def setup_produce(self):
        """Send request A to weblog : this request will produce a kafka message
        send request B to library buddy, this request will consume kafka message
        """

        self.production_response = weblog.get(
            "/kafka/produce",
            params={
                "topic": self.WEBLOG_TO_BUDDY_TOPIC,
                "integration": self.tracer_to_integration.get(context.library.name, None),
            },
            timeout=60,
        )

        self.consume_response = self.buddy.get(
            "/kafka/consume",
            params={
                "topic": self.WEBLOG_TO_BUDDY_TOPIC,
                "timeout": 60,
                "integration": self.tracer_to_integration.get(context.library.name, None),
            },
            timeout=61,
        )

    def test_produce(self):
        """Check that a message produced to kafka is correctly ingested by a Datadog python tracer"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The weblog is the producer, the buddy is the consumer
        self.validate_kafka_spans(
            producer_interface=interfaces.library,
            consumer_interface=self.buddy_interface,
            topic=self.WEBLOG_TO_BUDDY_TOPIC,
        )

    @missing_feature(
        library="ruby", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    def test_produce_trace_equality(self):
        """This test relies on the setup for produce, it currently cannot be run on its own"""
        producer_span = self.get_span(interfaces.library, span_kind="producer", topic=self.WEBLOG_TO_BUDDY_TOPIC)
        consumer_span = self.get_span(self.buddy_interface, span_kind="consumer", topic=self.WEBLOG_TO_BUDDY_TOPIC)

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span is not None
        assert consumer_span is not None
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def setup_consume(self):
        """Send request A to library buddy : this request will produce a kafka message
        send request B to weblog, this request will consume kafka message

        request A: GET /library_buddy/produce_kafka_message
        request B: GET /weblog/consume_kafka_message
        """
        self.production_response = self.buddy.get(
            "/kafka/produce",
            params={
                "topic": self.BUDDY_TO_WEBLOG_TOPIC,
                "integration": self.tracer_to_integration.get(context.library.name, None),
            },
            timeout=60,
        )

        self.consume_response = weblog.get(
            "/kafka/consume",
            params={
                "topic": self.BUDDY_TO_WEBLOG_TOPIC,
                "timeout": 60,
                "integration": self.tracer_to_integration.get(context.library.name, None),
            },
            timeout=61,
        )

    def test_consume(self):
        """Check that a message by an app instrumented by a Datadog python tracer is correctly ingested"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The buddy is the producer, the weblog is the consumer
        self.validate_kafka_spans(
            producer_interface=self.buddy_interface,
            consumer_interface=interfaces.library,
            topic=self.BUDDY_TO_WEBLOG_TOPIC,
        )

    @missing_feature(
        library="ruby", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    def test_consume_trace_equality(self):
        """This test relies on the setup for consume, it currently cannot be run on its own"""
        producer_span = self.get_span(self.buddy_interface, span_kind="producer", topic=self.BUDDY_TO_WEBLOG_TOPIC)
        consumer_span = self.get_span(interfaces.library, span_kind="consumer", topic=self.BUDDY_TO_WEBLOG_TOPIC)

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span is not None
        assert consumer_span is not None
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def validate_kafka_spans(self, producer_interface, consumer_interface, topic):
        """Validates production/consumption of kafka message.
        It works the same for both test_produce and test_consume
        """

        # Check that the producer did not created any consumer span
        assert self.get_span(producer_interface, span_kind="consumer", topic=topic) is None

        # Check that the consumer did not created any producer span
        assert self.get_span(consumer_interface, span_kind="producer", topic=topic) is None

        producer_span = self.get_span(producer_interface, span_kind="producer", topic=topic)
        consumer_span = self.get_span(consumer_interface, span_kind="consumer", topic=topic)
        # check that both consumer and producer spans exists
        assert producer_span is not None
        assert consumer_span is not None

        consumed = consumer_span["meta"].get("kafka.received_message")
        if consumed is not None:  # available only for python spans
            assert consumed == "True"

        # Assert that the consumer span is not the root
        assert "parent_id" in consumer_span, "parent_id is missing in consumer span"

        # returns both span for any custom check
        return producer_span, consumer_span


@scenarios.crossed_tracing_libraries
@features.kafkaspan_creationcontext_propagation_with_dd_trace
class Test_Kafka(_BaseKafka):
    buddy_interface = interfaces.java_buddy
    buddy = java_buddy
    WEBLOG_TO_BUDDY_TOPIC = "Test_Kafka_weblog_to_buddy"
    BUDDY_TO_WEBLOG_TOPIC = "Test_Kafka_buddy_to_weblog"
    tracer_to_integration = {
        "nodejs": "kafkajs",
    }

    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    def test_produce_trace_equality(self):
        super().test_produce_trace_equality()

    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    def test_consume_trace_equality(self):
        super().test_consume_trace_equality()


@scenarios.crossed_tracing_libraries
@features.kafkaspan_creationcontext_propagation_with_dd_trace
class Test_Kafka_Additional_Library(_BaseKafka):
    buddy_interface = interfaces.java_buddy
    buddy = java_buddy
    WEBLOG_TO_BUDDY_TOPIC = "Test_Kafka_2_weblog_to_buddy"
    BUDDY_TO_WEBLOG_TOPIC = "Test_Kafka_2_buddy_to_weblog"
    tracer_to_integration = {
        "nodejs": "@confluentinc/kafka-javascript",
    }

    @missing_feature(library="python", reason="Expected to fail, Python does not have an additional Kafka library")
    @missing_feature(library="java", reason="Expected to fail, Java does not have an additional Kafka library")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not have an additional Kafka library")
    @missing_feature(library="golang", reason="Expected to fail, Golang does not have an additional Kafka library")
    @missing_feature(library="dotnet", reason="Expected to fail, Dotnet does not have an additional Kafka library")
    @missing_feature(library="php", reason="Expected to fail, PHP does not have an additional Kafka library")
    def test_produce_trace_equality(self):
        super().test_produce_trace_equality()

    @missing_feature(library="python", reason="Expected to fail, Python does not have an additional Kafka library")
    @missing_feature(library="java", reason="Expected to fail, Java does not have an additional Kafka library")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not have an additional Kafka library")
    @missing_feature(library="golang", reason="Expected to fail, Golang does not have an additional Kafka library")
    @missing_feature(library="dotnet", reason="Expected to fail, Dotnet does not have an additional Kafka library")
    @missing_feature(library="php", reason="Expected to fail, PHP does not have an additional Kafka library")
    def test_consume_trace_equality(self):
        super().test_consume_trace_equality()
