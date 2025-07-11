from __future__ import annotations
import json

from utils.buddies import python_buddy, _Weblog as Weblog
from utils import interfaces, scenarios, weblog, missing_feature, features, context, logger


class _BaseKinesis:
    """Test Kinesis compatibility with inputted datadog tracer"""

    BUDDY_TO_WEBLOG_STREAM: str
    WEBLOG_TO_BUDDY_STREAM: str
    buddy: Weblog
    buddy_interface: interfaces.LibraryInterfaceValidator
    unique_id: str

    @classmethod
    def get_span(cls, interface, span_kind, stream, operation) -> dict | None:
        logger.debug(f"Trying to find traces with span kind: {span_kind} and stream: {stream} in {interface}")

        for data, trace in interface.get_traces():
            for span in trace:
                if not span.get("meta"):
                    continue

                if span["meta"].get("span.kind") not in span_kind:
                    continue

                # we want to skip all the kafka spans
                if "aws.service" not in span["meta"] and "aws_service" not in span["meta"]:
                    continue

                if (
                    "kinesis" not in span["meta"].get("aws.service", "").lower()
                    and "kinesis" not in span["meta"].get("aws_service", "").lower()
                ):
                    continue

                if operation.lower() != span["meta"].get("aws.operation", "").lower():
                    continue

                if operation.lower() == "getrecords" and span["meta"].get("language", "") == "javascript":
                    # for nodejs we propagate from aws.response span which does not have the stream included on the span.
                    if span["resource"] != "aws.response":
                        continue
                # elif stream != cls.get_stream_name(span):
                #     continue

                logger.debug(f"span found in {data['log_filename']}:\n{json.dumps(span, indent=2)}")
                return span

        logger.debug("No span found")
        return None

    @staticmethod
    def get_stream(span) -> str | None:
        """Extracts the stream from a span by trying various fields"""
        stream = span["meta"].get("streamname", None)  # this is in nodejs, java, python

        if stream is None:
            if "aws.stream.url" in span["meta"]:
                stream = span["meta"]["aws.stream.url"].split("/")[-1]
            elif "messaging.url" in span["meta"]:
                stream = span["meta"]["messaging.url"].split("/")[-1]

            if stream is None:
                logger.error(f"could not extract stream from this span:\n{span}")

        return stream

    def setup_produce(self):
        """Send request A to weblog : this request will produce a Kinesis message
        send request B to library buddy, this request will consume Kinesis message
        """
        message = (
            "[crossed_integrations/test_kinesis.py][Kinesis] Hello from Kinesis "
            f"[{context.library.name} weblog->{self.buddy_interface.name}] test produce at {self.unique_id}"
        )

        self.production_response = weblog.get(
            "/kinesis/produce", params={"stream": self.WEBLOG_TO_BUDDY_STREAM, "message": message}, timeout=120
        )
        self.consume_response = self.buddy.get(
            "/kinesis/consume",
            params={"stream": self.WEBLOG_TO_BUDDY_STREAM, "message": message, "timeout": 60},
            timeout=61,
        )

    def test_produce(self):
        """Check that a message produced to Kinesis is correctly ingested by a Datadog tracer"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The weblog is the producer, the buddy is the consumer
        self.validate_kinesis_spans(
            producer_interface=interfaces.library,
            consumer_interface=self.buddy_interface,
            stream=self.WEBLOG_TO_BUDDY_STREAM,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    @missing_feature(
        library="java", reason="Expected to fail, Java defaults to using Xray headers to propagate context"
    )
    def test_produce_trace_equality(self):
        """This test relies on the setup for produce, it currently cannot be run on its own"""
        producer_span = self.get_span(
            interfaces.library,
            span_kind=["producer", "client"],
            stream=self.WEBLOG_TO_BUDDY_STREAM,
            operation="PutRecord",
        )
        consumer_span = self.get_span(
            self.buddy_interface,
            span_kind=["consumer", "client", "server"],
            stream=self.WEBLOG_TO_BUDDY_STREAM,
            operation="GetRecords",
        )

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span is not None
        assert consumer_span is not None
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def setup_consume(self):
        """Send request A to library buddy : this request will produce a Kinesis message
        send request B to weblog, this request will consume Kinesis message

        request A: GET /library_buddy/produce_kinesis_message
        request B: GET /weblog/consume_kinesis_message
        """
        message = (
            "[crossed_integrations/test_kinesis.py][Kinesis] Hello from Kinesis "
            f"[{self.buddy_interface.name}->{context.library.name} weblog] test consume at {self.unique_id}"
        )

        self.production_response = self.buddy.get(
            "/kinesis/produce", params={"stream": self.BUDDY_TO_WEBLOG_STREAM, "message": message}, timeout=500
        )
        self.consume_response = weblog.get(
            "/kinesis/consume",
            params={"stream": self.BUDDY_TO_WEBLOG_STREAM, "message": message, "timeout": 60},
            timeout=61,
        )

    def test_consume(self):
        """Check that a message by an app instrumented by a Datadog tracer is correctly ingested"""

        assert self.production_response.status_code == 200
        assert self.consume_response.status_code == 200

        # The buddy is the producer, the weblog is the consumer
        self.validate_kinesis_spans(
            producer_interface=self.buddy_interface,
            consumer_interface=interfaces.library,
            stream=self.BUDDY_TO_WEBLOG_STREAM,
        )

    @missing_feature(library="golang", reason="Expected to fail, Golang does not propagate context")
    @missing_feature(library="ruby", reason="Expected to fail, Ruby does not propagate context")
    @missing_feature(
        library="java", reason="Expected to fail, Java does not extract message attribute context for Kinesis"
    )
    def test_consume_trace_equality(self):
        """This test relies on the setup for consume, it currently cannot be run on its own"""
        producer_span = self.get_span(
            self.buddy_interface,
            span_kind=["producer", "client"],
            stream=self.BUDDY_TO_WEBLOG_STREAM,
            operation="PutRecord",
        )
        consumer_span = self.get_span(
            interfaces.library,
            span_kind=["consumer", "client", "server"],
            stream=self.BUDDY_TO_WEBLOG_STREAM,
            operation="GetRecords",
        )

        # Both producer and consumer spans should be part of the same trace
        # Different tracers can handle the exact propagation differently, so for now, this test avoids
        # asserting on direct parent/child relationships
        assert producer_span is not None
        assert consumer_span is not None
        assert producer_span["trace_id"] == consumer_span["trace_id"]

    def validate_kinesis_spans(self, producer_interface, consumer_interface, stream):
        """Validates production/consumption of Kinesis message.
        It works the same for both test_produce and test_consume
        """

        producer_span = self.get_span(
            producer_interface, span_kind=["producer", "client"], stream=stream, operation="PutRecord"
        )
        consumer_span = self.get_span(
            consumer_interface, span_kind=["consumer", "client", "server"], stream=stream, operation="GetRecords"
        )
        # check that both consumer and producer spans exists
        assert producer_span is not None
        assert consumer_span is not None

        # returns both span for any custom check
        return producer_span, consumer_span


@scenarios.crossed_tracing_libraries
@features.aws_kinesis_span_creationcontext_propagation_via_message_attributes_with_dd_trace
class Test_Kinesis_PROPAGATION_VIA_MESSAGE_ATTRIBUTES(_BaseKinesis):
    buddy_interface = interfaces.python_buddy
    buddy = python_buddy

    unique_id = scenarios.crossed_tracing_libraries.unique_id
    WEBLOG_TO_BUDDY_STREAM = f"Kinesis_prop_via_msg_attributes_weblog_to_buddy_{unique_id}"
    BUDDY_TO_WEBLOG_STREAM = f"Kinesis_prop_via_msg_attributes_buddy_to_weblog_{unique_id}"
