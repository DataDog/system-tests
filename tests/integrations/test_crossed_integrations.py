from __future__ import annotations

import json

from utils import interfaces, scenarios, coverage, weblog, missing_feature, features
from utils._weblog import _Weblog
from utils.tools import logger


# TODO: move this class in utils
class _PythonBuddy(_Weblog):
    def __init__(self):
        from collections import defaultdict

        self.port = 9001
        self.domain = "localhost"

        self.responses = defaultdict(list)
        self.current_nodeid = "not used"
        self.replay = False


# TODO: move this class in utils
class _NodeJSBuddy(_Weblog):
    def __init__(self):
        from collections import defaultdict

        self.port = 9002
        self.domain = "localhost"

        self.responses = defaultdict(list)
        self.current_nodeid = "not used"
        self.replay = False


@scenarios.crossed_tracing_libraries
@coverage.basic
@features.kafkaspan_creationcontext_propagation_with_dd_trace_py
class Test_PythonKafka:
    """Test kafka compatibility with datadog python tracer"""

    WEBLOG_TO_BUDDY_TOPIC = "Test_PythonKafka_weblog_to_buddy"
    BUDDY_TO_WEBLOG_TOPIC = "Test_PythonKafka_buddy_to_weblog"

    @classmethod
    def get_span(cls, interface, span_kind, topic):
        logger.debug(f"Trying to find traces with span kind: {span_kind} and topic: {topic} in {interface}")

        for data, trace in interface.get_traces():
            print(trace)
            for span in trace:
                print(span)
                if type(span) != dict:
                    continue

                if span.get('meta', {}) == {}:
                    continue

                if span_kind != span["meta"].get("span.kind"):
                    continue

                if topic != cls.get_topic(span):
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
        """
        send request A to weblog : this request will produce a kafka message
        send request B to python buddy, this request will consume kafka message
        """

        python_buddy = _PythonBuddy()

        self.production_response = weblog.get("/kafka/produce", params={"topic": self.WEBLOG_TO_BUDDY_TOPIC})
        self.consume_response = python_buddy.get("/kafka/consume", params={"topic": self.WEBLOG_TO_BUDDY_TOPIC})

    def test_produce(self):
        """Check that a message produced to kafka is correctly ingested by a Datadog python tracer"""

        assert self.production_response.status_code == 200

        # The weblog is the producer, the buddy is the consumer
        self.validate_kafka_spans(
            producer_interface=interfaces.library,
            consumer_interface=interfaces.python_buddy,
            topic=self.WEBLOG_TO_BUDDY_TOPIC,
        )

    @missing_feature(
        library="nodejs", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    @missing_feature(
        library="python", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    @missing_feature(
        library="java", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    @missing_feature(
        library="golang", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    @missing_feature(
        library="ruby", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    def test_produce_trace_equality(self):
        """This test relies on the setup for produce, it currently cannot be run on its own"""
        producer_span = self.get_span(interfaces.library, span_kind="producer", topic=self.WEBLOG_TO_BUDDY_TOPIC)
        consumer_span = self.get_span(interfaces.python_buddy, span_kind="consumer", topic=self.WEBLOG_TO_BUDDY_TOPIC)

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def setup_consume(self):
        """
        send request A to python buddy : this request will produce a kafka message
        send request B to weblog, this request will consume kafka message

        request A: GET /python_buddy/produce_kafka_message
        request B: GET /weblog/consume_kafka_message
        """
        python_buddy = _PythonBuddy()

        self.production_response = python_buddy.get("/kafka/produce", params={"topic": self.BUDDY_TO_WEBLOG_TOPIC})
        self.consume_response = weblog.get("/kafka/consume", params={"topic": self.BUDDY_TO_WEBLOG_TOPIC})

    def test_consume(self):
        """Check that a message by an app instrumented by a Datadog python tracer is correctly ingested"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The buddy is the producer, the weblog is the consumer
        self.validate_kafka_spans(
            producer_interface=interfaces.python_buddy,
            consumer_interface=interfaces.library,
            topic=self.BUDDY_TO_WEBLOG_TOPIC,
        )

    @missing_feature(
        library="nodejs", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    @missing_feature(
        library="python", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    @missing_feature(
        library="java", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    @missing_feature(
        library="golang", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    @missing_feature(
        library="ruby", reason="Expected to fail, one end is always Python which does not currently propagate context"
    )
    def test_consume_trace_equality(self):
        """This test relies on the setup for consume, it currently cannot be run on its own"""
        producer_span = self.get_span(interfaces.python_buddy, span_kind="producer", topic=self.BUDDY_TO_WEBLOG_TOPIC)
        consumer_span = self.get_span(interfaces.library, span_kind="consumer", topic=self.BUDDY_TO_WEBLOG_TOPIC)

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def validate_kafka_spans(self, producer_interface, consumer_interface, topic):
        """
        Validates production/consumption of kafka message.
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
@coverage.basic
@features.kafkaspan_creationcontext_propagation_with_dd_trace_js
class Test_NodeJSKafka:
    """Test kafka compatibility with datadog nodejs tracer"""

    WEBLOG_TO_BUDDY_TOPIC = "Test_NodeJSKafka_weblog_to_buddy"
    BUDDY_TO_WEBLOG_TOPIC = "Test_NodeJSKafka_buddy_to_weblog"

    @classmethod
    def get_span(cls, interface, span_kind, topic):
        logger.debug(f"Trying to find traces with span kind: {span_kind} and topic: {topic} in {interface}")

        for data, trace in interface.get_traces():
            print(trace)
            for span in trace:
                print(span)
                if type(span) != dict:
                    continue

                if span.get('meta', {}) == {}:
                    continue

                if span_kind != span["meta"].get("span.kind"):
                    continue

                if topic != cls.get_topic(span):
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
        """
        send request A to weblog : this request will produce a kafka message
        send request B to nodejs buddy, this request will consume kafka message
        """

        nodejs_buddy = _NodeJSBuddy()

        self.production_response = weblog.get("/kafka/produce", params={"topic": self.WEBLOG_TO_BUDDY_TOPIC})
        self.consume_response = nodejs_buddy.get("/kafka/consume", params={"topic": self.WEBLOG_TO_BUDDY_TOPIC})

    def test_produce(self):
        """Check that a message produced to kafka is correctly ingested by a Datadog python tracer"""

        assert self.production_response.status_code == 200

        # The weblog is the producer, the buddy is the consumer
        self.validate_kafka_spans(
            producer_interface=interfaces.library,
            consumer_interface=interfaces.nodejs_buddy,
            topic=self.WEBLOG_TO_BUDDY_TOPIC,
        )

    # @missing_feature(
    #     library="nodejs", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    # )
    @missing_feature(
        library="python", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    )
    @missing_feature(
        library="java", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    )
    @missing_feature(
        library="golang", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    )
    @missing_feature(
        library="ruby", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    )
    def test_produce_trace_equality(self):
        """This test relies on the setup for produce, it currently cannot be run on its own"""
        producer_span = self.get_span(interfaces.library, span_kind="producer", topic=self.WEBLOG_TO_BUDDY_TOPIC)
        consumer_span = self.get_span(interfaces.nodejs_buddy, span_kind="consumer", topic=self.WEBLOG_TO_BUDDY_TOPIC)

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def setup_consume(self):
        """
        send request A to nodejs buddy : this request will produce a kafka message
        send request B to weblog, this request will consume kafka message

        request A: GET /nodejs_buddy/produce_kafka_message
        request B: GET /weblog/consume_kafka_message
        """
        nodejs_buddy = _NodeJSBuddy()

        self.production_response = nodejs_buddy.get("/kafka/produce", params={"topic": self.BUDDY_TO_WEBLOG_TOPIC})
        self.consume_response = weblog.get("/kafka/consume", params={"topic": self.BUDDY_TO_WEBLOG_TOPIC})

    def test_consume(self):
        """Check that a message by an app instrumented by a Datadog python tracer is correctly ingested"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The buddy is the producer, the weblog is the consumer
        self.validate_kafka_spans(
            producer_interface=interfaces.nodejs_buddy,
            consumer_interface=interfaces.library,
            topic=self.BUDDY_TO_WEBLOG_TOPIC,
        )

    # @missing_feature(
    #     library="nodejs", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    # )
    @missing_feature(
        library="python", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    )
    @missing_feature(
        library="java", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    )
    @missing_feature(
        library="golang", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    )
    @missing_feature(
        library="ruby", reason="Expected to fail, one end is always NodeJS which does not currently propagate context"
    )
    def test_consume_trace_equality(self):
        """This test relies on the setup for consume, it currently cannot be run on its own"""
        producer_span = self.get_span(interfaces.nodejs_buddy, span_kind="producer", topic=self.BUDDY_TO_WEBLOG_TOPIC)
        consumer_span = self.get_span(interfaces.library, span_kind="consumer", topic=self.BUDDY_TO_WEBLOG_TOPIC)

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def validate_kafka_spans(self, producer_interface, consumer_interface, topic):
        """
        Validates production/consumption of kafka message.
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
