from __future__ import annotations
import json

from utils.buddies import python_buddy, _Weblog as Weblog
from utils import interfaces, scenarios, weblog, missing_feature, features, context, logger


class _BaseSNS:
    """Test sns compatibility with inputted datadog tracer"""

    BUDDY_TO_WEBLOG_QUEUE: str
    BUDDY_TO_WEBLOG_TOPIC: str
    WEBLOG_TO_BUDDY_QUEUE: str
    WEBLOG_TO_BUDDY_TOPIC: str
    buddy: Weblog
    buddy_interface: interfaces.LibraryInterfaceValidator
    unique_id: str

    @classmethod
    def get_span(cls, interface, span_kind, queue, topic, operation) -> dict | None:
        logger.debug(f"Trying to find traces with span kind: {span_kind} and queue: {queue} in {interface}")
        manual_span_found = False

        for data, trace in interface.get_traces():
            # we iterate the trace backwards to deal with the case of JS "aws.response" callback spans, which are similar for this test and test_sqs.
            # Instead, we look for the custom span created after the "aws.response" span
            for span in reversed(trace):
                if not span.get("meta"):
                    continue

                # special case for JS spans where we create a manual span since the callback span lacks specific information
                if (
                    span["meta"].get("language", "") == "javascript"
                    and span["name"] == "sns.consume"
                    and span["meta"].get("queue_name", "") == queue
                ):
                    manual_span_found = True
                    continue

                if span["meta"].get("span.kind") not in span_kind:
                    continue

                # we want to skip all the kafka spans
                if "aws.service" not in span["meta"] and "aws_service" not in span["meta"]:
                    continue

                if span["meta"].get("aws.service", span["meta"].get("aws_service", "")).lower() not in ["sns", "sqs"]:
                    continue

                if operation.lower() != span["meta"].get("aws.operation", "").lower():
                    continue

                if operation.lower() == "publish":
                    if topic != cls.get_topic(span):
                        continue
                elif operation.lower() == "receivemessage" and span["meta"].get("language", "") == "javascript":
                    # for nodejs we propagate from aws.response span which does not have the queue included on the span
                    if span["resource"] != "aws.response" or not manual_span_found:
                        continue
                elif queue != cls.get_queue(span):
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
            elif "messaging.url" in span["meta"]:
                queue = span["meta"]["messaging.url"].split("/")[-1]

            if queue is None:
                logger.error(f"could not extract queue from this span:\n{span}")

        return queue

    @staticmethod
    def get_topic(span) -> str | None:
        """Extracts the topic from a span by trying various fields"""
        topic = span["meta"].get("topicname", None)  # this is in nodejs, java, python

        if topic is None:
            if "aws.sns.topic_arn" in span["meta"]:
                topic = span["meta"]["aws.sns.topic_arn"].split(":")[-1]
            if topic is None:
                logger.error(f"could not extract topic from this span:\n{span}")

        return topic

    def setup_produce(self):
        """Send request A to weblog : this request will produce a sns message
        send request B to library buddy, this request will consume sns message
        """
        message = (
            "[crossed_integrations/test_sns_to_sqs.py][SNS] Hello from SNS "
            f"[{context.library.name} weblog->{self.buddy_interface.name}] test produce at {self.unique_id}"
        )

        self.production_response = weblog.get(
            "/sns/produce",
            params={"queue": self.WEBLOG_TO_BUDDY_QUEUE, "topic": self.WEBLOG_TO_BUDDY_TOPIC, "message": message},
            timeout=60,
        )
        self.consume_response = self.buddy.get(
            "/sns/consume",
            params={"queue": self.WEBLOG_TO_BUDDY_QUEUE, "timeout": 60, "message": message},
            timeout=61,
        )

    def test_produce(self):
        """Check that a message produced to sns is correctly ingested by a Datadog tracer"""
        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The weblog is the producer, the buddy is the consumer
        self.validate_sns_spans(
            producer_interface=interfaces.library,
            consumer_interface=self.buddy_interface,
            queue=self.WEBLOG_TO_BUDDY_QUEUE,
            topic=self.WEBLOG_TO_BUDDY_TOPIC,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    def test_produce_trace_equality(self):
        """This test relies on the setup for produce, it currently cannot be run on its own"""
        producer_span = self.get_span(
            interfaces.library,
            span_kind=["producer", "client"],
            queue=self.WEBLOG_TO_BUDDY_QUEUE,
            topic=self.WEBLOG_TO_BUDDY_TOPIC,
            operation="publish",
        )
        consumer_span = self.get_span(
            self.buddy_interface,
            span_kind=["consumer", "client", "server"],
            queue=self.WEBLOG_TO_BUDDY_QUEUE,
            topic=self.WEBLOG_TO_BUDDY_TOPIC,
            operation="receiveMessage",
        )

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span is not None
        assert consumer_span is not None
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def setup_consume(self):
        """Send request A to library buddy : this request will produce a sns message
        send request B to weblog, this request will consume sns message

        request A: GET /library_buddy/produce_sns_message
        request B: GET /weblog/consume_sns_message
        """
        message = (
            "[crossed_integrations/test_sns_to_sqs.py][SNS] Hello from SNS "
            f"[{self.buddy_interface.name}->{context.library.name} weblog] test consume at {self.unique_id}"
        )

        self.production_response = self.buddy.get(
            "/sns/produce",
            params={"queue": self.BUDDY_TO_WEBLOG_QUEUE, "topic": self.BUDDY_TO_WEBLOG_TOPIC, "message": message},
            timeout=60,
        )
        self.consume_response = weblog.get(
            "/sns/consume",
            params={"queue": self.BUDDY_TO_WEBLOG_QUEUE, "timeout": 60, "message": message},
            timeout=61,
        )

    def test_consume(self):
        """Check that a message by an app instrumented by a Datadog tracer is correctly ingested"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The buddy is the producer, the weblog is the consumer
        self.validate_sns_spans(
            producer_interface=self.buddy_interface,
            consumer_interface=interfaces.library,
            queue=self.BUDDY_TO_WEBLOG_QUEUE,
            topic=self.BUDDY_TO_WEBLOG_TOPIC,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    def test_consume_trace_equality(self):
        """This test relies on the setup for consume, it currently cannot be run on its own"""
        producer_span = self.get_span(
            self.buddy_interface,
            span_kind=["producer", "client"],
            queue=self.BUDDY_TO_WEBLOG_QUEUE,
            topic=self.BUDDY_TO_WEBLOG_TOPIC,
            operation="publish",
        )
        consumer_span = self.get_span(
            interfaces.library,
            span_kind=["consumer", "client", "server"],
            queue=self.BUDDY_TO_WEBLOG_QUEUE,
            topic=self.BUDDY_TO_WEBLOG_TOPIC,
            operation="receiveMessage",
        )

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span is not None
        assert consumer_span is not None
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def validate_sns_spans(self, producer_interface, consumer_interface, queue, topic):
        """Validates production/consumption of sns message.
        It works the same for both test_produce and test_consume
        """

        producer_span = self.get_span(
            producer_interface, span_kind=["producer", "client"], queue=queue, topic=topic, operation="publish"
        )
        consumer_span = self.get_span(
            consumer_interface,
            span_kind=["consumer", "client", "server"],
            queue=queue,
            topic=topic,
            operation="receiveMessage",
        )
        # check that both consumer and producer spans exists
        assert producer_span is not None
        assert consumer_span is not None

        # Assert that the consumer span is not the root
        assert "parent_id" in consumer_span, "parent_id is missing in consumer span"

        # returns both span for any custom check
        return producer_span, consumer_span


@scenarios.crossed_tracing_libraries
@features.aws_sns_span_creationcontext_propagation_via_message_attributes_with_dd_trace
class Test_SNS_Propagation(_BaseSNS):
    buddy_interface = interfaces.python_buddy
    buddy = python_buddy

    unique_id = scenarios.crossed_tracing_libraries.unique_id

    WEBLOG_TO_BUDDY_QUEUE = f"SNS_Propagation_msg_attributes_weblog_to_buddy_{unique_id}"
    WEBLOG_TO_BUDDY_TOPIC = f"SNS_Propagation_msg_attributes_weblog_to_buddy_topic_{unique_id}"
    BUDDY_TO_WEBLOG_QUEUE = f"SNS_Propagation_msg_attributes_buddy_to_weblog_{unique_id}"
    BUDDY_TO_WEBLOG_TOPIC = f"SNS_Propagation_msg_attributes_buddy_to_weblog_topic_{unique_id}"
