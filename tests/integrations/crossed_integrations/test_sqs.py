from __future__ import annotations

import json
import time

from tests.integrations.crossed_integrations.test_kafka import _python_buddy, _nodejs_buddy, _java_buddy, hit_timeout
from utils import interfaces, scenarios, coverage, weblog, missing_feature, features, context, irrelevant
from utils.tools import logger


class _Test_SQS:
    """Test sqs compatibility with inputted datadog tracer"""

    @classmethod
    def get_span(cls, interface, span_kind, queue):
        logger.debug(f"Trying to find traces with span kind: {span_kind} and queue: {queue} in {interface}")

        for data, trace in interface.get_traces():
            for span in trace:
                if not span.get("meta"):
                    continue

                if span_kind != span["meta"].get("span.kind"):
                    continue

                # we want to skip all the kafka spans
                if "aws" not in span["resource"].lower():
                    continue

                if queue != cls.get_queue(span):
                    continue

                logger.debug(f"span found in {data['log_filename']}:\n{json.dumps(span, indent=2)}")
                return span

        logger.debug("No span found")
        return None

    @staticmethod
    def get_queue(span) -> str | None:
        """Extracts the queue from a span by trying various fields"""
        queue = span["meta"].get("queuename", None)  # this is in nodejs, java, python

        if queue is None:
            if "aws.queue.url" in span["meta"]:
                queue = span["meta"]["aws.queue.url"].split("/")[-1]

            if queue is None:
                logger.error(f"could not extract queue from this span:\n{span}")

        return queue

    def setup_produce(self):
        """
        send request A to weblog : this request will produce a sqs message
        send request B to library buddy, this request will consume sqs message
        """
        timeout = time.time() + 300

        self.production_response = None
        self.consume_response = None
        while (
            self.production_response is None
            or self.production_response.status_code != 200
            or self.production_response.text is None
        ):
            self.production_response = weblog.get(
                "/sqs/produce", params={"queue": self.WEBLOG_TO_BUDDY_QUEUE}, timeout=5
            )
            if hit_timeout(self, timeout):
                break

        while (
            self.consume_response is None
            or self.consume_response.status_code != 200
            or self.consume_response.text is None
        ):
            self.consume_response = self.buddy.get(
                "/sqs/consume", params={"queue": self.WEBLOG_TO_BUDDY_QUEUE, "timeout": 5}, timeout=5
            )
            if hit_timeout(self, timeout):
                break

    def test_produce(self):
        """Check that a message produced to sqs is correctly ingested by a Datadog python tracer"""

        assert self.production_response.status_code == 200

        # The weblog is the producer, the buddy is the consumer
        self.validate_sqs_spans(
            producer_interface=interfaces.library,
            consumer_interface=self.buddy_interface,
            queue=self.WEBLOG_TO_BUDDY_QUEUE,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    @missing_feature(library="python", reason="Expected to fail, Python does not propagate context")
    @missing_feature(library="nodejs", reason="Expected to fail, Nodejs does not propagate context")
    @missing_feature(library="java", reason="Expected to fail, Nodejs does not propagate context")
    def test_produce_trace_equality(self):
        """This test relies on the setup for produce, it currently cannot be run on its own"""
        producer_span = self.get_span(interfaces.library, span_kind="producer", queue=self.WEBLOG_TO_BUDDY_QUEUE)
        consumer_span = self.get_span(self.buddy_interface, span_kind="consumer", queue=self.WEBLOG_TO_BUDDY_QUEUE)

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def setup_consume(self):
        """
        send request A to library buddy : this request will produce a sqs message
        send request B to weblog, this request will consume sqs message

        request A: GET /library_buddy/produce_sqs_message
        request B: GET /weblog/consume_sqs_message
        """
        timeout = time.time() + 300
        self.production_response = None
        self.consume_response = None
        while (
            self.production_response is None
            or self.production_response.status_code != 200
            or self.production_response.text is None
        ):
            self.production_response = self.buddy.get(
                "/sqs/produce", params={"queue": self.BUDDY_TO_WEBLOG_QUEUE}, timeout=5
            )
            if hit_timeout(self, timeout):
                break

        while (
            self.consume_response is None
            or self.consume_response.status_code != 200
            or self.consume_response.text is None
        ):
            self.consume_response = weblog.get(
                "/sqs/consume", params={"queue": self.BUDDY_TO_WEBLOG_QUEUE, "timeout": 5}, timeout=5
            )
            if hit_timeout(self, timeout):
                break

    def test_consume(self):
        """Check that a message by an app instrumented by a Datadog python tracer is correctly ingested"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The buddy is the producer, the weblog is the consumer
        self.validate_sqs_spans(
            producer_interface=self.buddy_interface,
            consumer_interface=interfaces.library,
            queue=self.BUDDY_TO_WEBLOG_QUEUE,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    @missing_feature(library="python", reason="Expected to fail, Python does not propagate context")
    @missing_feature(library="nodejs", reason="Expected to fail, Nodejs does not propagate context")
    @missing_feature(library="java", reason="Expected to fail, Nodejs does not propagate context")
    def test_consume_trace_equality(self):
        """This test relies on the setup for consume, it currently cannot be run on its own"""
        producer_span = self.get_span(self.buddy_interface, span_kind="producer", queue=self.BUDDY_TO_WEBLOG_QUEUE)
        consumer_span = self.get_span(interfaces.library, span_kind="consumer", queue=self.BUDDY_TO_WEBLOG_QUEUE)

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def validate_sqs_spans(self, producer_interface, consumer_interface, queue):
        """
        Validates production/consumption of sqs message.
        It works the same for both test_produce and test_consume
        """

        # Check that the producer did not created any consumer span
        assert self.get_span(producer_interface, span_kind="consumer", queue=queue) is None

        # Check that the consumer did not created any producer span
        assert self.get_span(consumer_interface, span_kind="producer", queue=queue) is None

        producer_span = self.get_span(producer_interface, span_kind="producer", queue=queue)
        consumer_span = self.get_span(consumer_interface, span_kind="consumer", queue=queue)
        # check that both consumer and producer spans exists
        assert producer_span is not None
        assert consumer_span is not None

        # consumed = consumer_span["meta"].get("sqs.received_message")
        # if consumed is not None:  # available only for python spans
        #     assert consumed == "True"

        # Assert that the consumer span is not the root
        assert "parent_id" in consumer_span, "parent_id is missing in consumer span"

        # returns both span for any custom check
        return producer_span, consumer_span


MISSING_LIBRARY_LOGIC = (
    context.library == "cpp"
    or context.library == "php"
    or context.library == "dotnet"
    or context.library == "golang"
    or context.library == "ruby"
    or (context.library == "python" and context.weblog_variant != "flask-poc")
    or (context.library == "java" and context.weblog_variant != "spring-boot")
    or (context.library == "nodejs" and context.weblog_variant != "express4")
)


@irrelevant(MISSING_LIBRARY_LOGIC)
@scenarios.crossed_tracing_libraries
@coverage.basic
@features.aws_sqs_span_creationcontext_propagation_with_dd_trace_js
class Test_NodeJS_SQS(_Test_SQS):
    buddy_interface = interfaces.nodejs_buddy
    buddy = _nodejs_buddy
    WEBLOG_TO_BUDDY_QUEUE = f"Test_NodeJS_SQS_weblog_to_buddy"
    BUDDY_TO_WEBLOG_QUEUE = f"Test_NodeJS_SQS_buddy_to_weblog"


@irrelevant(MISSING_LIBRARY_LOGIC)
@scenarios.crossed_tracing_libraries
@coverage.basic
@features.aws_sqs_span_creationcontext_propagation_with_dd_trace_py
class Test_Python_SQS(_Test_SQS):
    buddy_interface = interfaces.python_buddy
    buddy = _python_buddy
    WEBLOG_TO_BUDDY_QUEUE = f"Test_Python_SQS_weblog_to_buddy"
    BUDDY_TO_WEBLOG_QUEUE = f"Test_Python_SQS_buddy_to_weblog"


@irrelevant(MISSING_LIBRARY_LOGIC)
@scenarios.crossed_tracing_libraries
@coverage.basic
@features.aws_sqs_span_creationcontext_propagation_with_dd_trace_java
class Test_Java_SQS(_Test_SQS):
    buddy_interface = interfaces.java_buddy
    buddy = _java_buddy
    WEBLOG_TO_BUDDY_QUEUE = f"Test_Java_SQS_weblog_to_buddy"
    BUDDY_TO_WEBLOG_QUEUE = f"Test_Java_SQS_buddy_to_weblog"

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    @missing_feature(library="python", reason="Expected to fail, Python does not propagate context")
    @missing_feature(library="nodejs", reason="Expected to fail, Nodejs does not propagate context")
    def test_produce_trace_equality(self):
        super().test_produce_trace_equality()

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    @missing_feature(library="python", reason="Expected to fail, Python does not propagate context")
    @missing_feature(library="nodejs", reason="Expected to fail, Nodejs does not propagate context")
    def test_consume_trace_equality(self):
        super().test_consume_trace_equality()
