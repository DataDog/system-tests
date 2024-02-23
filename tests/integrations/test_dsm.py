# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, scenarios, irrelevant, context, bug, features, missing_feature
from utils.tools import logger

import logging

import kombu


@features.datastreams_monitoring_support_for_kafka
@scenarios.integrations
class Test_DsmKafka:
    """ Verify DSM stats points for Kafka """

    def setup_dsm_kafka(self):
        self.r = weblog.get("/dsm?integration=kafka")

    def test_dsm_kafka(self):
        assert self.r.text == "ok"

        # Hashes are created by applying the FNV-1 algorithm on
        # checkpoint strings (e.g. service:foo)
        # There is currently no FNV-1 library availble for node.js
        # So we are using a different algorithm for node.js for now
        if context.library == "nodejs":
            producer_hash = 2931833227331067675
            consumer_hash = 271115008390912609
        else:
            producer_hash = 4463699290244539355
            consumer_hash = 3735318893869752335

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=("direction:out", "topic:dsm-system-tests-queue", "type:kafka"),
        )
        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash,
            parent_hash=producer_hash,
            tags=("direction:in", "group:testgroup1", "topic:dsm-system-tests-queue", "type:kafka"),
        )


@features.datastreams_monitoring_support_for_http
@scenarios.integrations
class Test_DsmHttp:
    def setup_dsm_http(self):
        # Note that for HTTP, we will still test using Kafka, because the call to Weblog itself is HTTP
        # and will be instrumented as such
        self.r = weblog.get("/dsm?integration=kafka")

    def test_dsm_http(self):
        assert self.r.text == "ok"

        DsmHelper.assert_checkpoint_presence(
            hash_=3883033147046472598, parent_hash=0, tags=("direction:in", "type:http")
        )


@features.datastreams_monitoring_support_for_rabbitmq
@scenarios.integrations
class Test_DsmRabbitmq:
    """ Verify DSM stats points for RabbitMQ """

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq")

    @bug(library="dotnet", reason="bug in dotnet behavior")
    def test_dsm_rabbitmq(self):
        assert self.r.text == "ok"

        # Hashes are created by applying the FNV-1 algorithm on
        # checkpoint strings (e.g. service:foo)
        # There is currently no FNV-1 library availble for node.js
        # So we are using a different algorithm for node.js for now
        if context.library == "nodejs":
            producer_hash = 5080618047473654667
            consumer_hash = 12436096712734841122
            # node does not have access to the queue argument and defaults to using the routing key
            edge_tags_in = ("direction:in", "topic:systemTestDirectRoutingKey", "type:rabbitmq")
            edge_tags_out = (
                "direction:out",
                "exchange:systemTestDirectExchange",
                "has_routing_key:true",
                "type:rabbitmq",
            )
        elif context.library == "python":
            producer_hash = 3519882823224826180
            consumer_hash = 13984784774671877513
            edge_tags_in = ("direction:in", "topic:dsm-system-tests-queue", "type:rabbitmq")
            edge_tags_out = (
                "direction:out",
                "exchange:dsm-system-tests-queue",
                "has_routing_key:true",
                "type:rabbitmq",
            )

        else:
            producer_hash = 6176024609184775446
            consumer_hash = 1648106384315938543
            edge_tags_in = ("direction:in", "topic:systemTestRabbitmqQueue", "type:rabbitmq")
            edge_tags_out = (
                "direction:out",
                "exchange:systemTestDirectExchange",
                "has_routing_key:true",
                "type:rabbitmq",
            )

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=edge_tags_out,
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in,
        )

    def setup_dsm_rabbitmq_dotnet_legacy(self):
        self.r = weblog.get("/dsm?integration=rabbitmq")

    @irrelevant(context.library != "dotnet" or context.library > "dotnet@2.33.0", reason="legacy dotnet behavior")
    def test_dsm_rabbitmq_dotnet_legacy(self):
        assert self.r.text == "ok"

        # Dotnet sets the tag for `has_routing_key` to `has_routing_key:True` instead of `has_routing_key:true` like
        # the other tracer libraries, which causes the resulting hash to be different.
        DsmHelper.assert_checkpoint_presence(
            hash_=12547013883960139159,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestDirectExchange", "has_routing_key:True", "type:rabbitmq"),
        )

        # There seems to be a bug in dotnet currently where the queue is not passed, causing DSM to default to setting
        # the routing key as the topic.
        # See https://github.com/DataDog/dd-trace-dotnet/blob/6aab5e1b02bec9c9b68a33cd06cc9e7a774f14de/tracer/src/Datadog.Trace/ClrProfiler/AutoInstrumentation/RabbitMQ/RabbitMQIntegration.cs#L144
        # where `queue` is not passed
        DsmHelper.assert_checkpoint_presence(
            hash_=12449081340987959886,
            parent_hash=12547013883960139159,
            tags=("direction:in", "topic:testRoutingKey", "type:rabbitmq"),
        )


@features.datastreams_monitoring_support_for_rabbitmq_topicexchange
@scenarios.integrations
class Test_DsmRabbitmq_TopicExchange:
    """ Verify DSM stats points for RabbitMQ Topic Exchange"""

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq_topic_exchange")

    def test_dsm_rabbitmq(self):
        assert self.r.text == "ok"

        DsmHelper.assert_checkpoint_presence(
            hash_=18436203392999142109,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestTopicExchange", "has_routing_key:true", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=11364757106893616177,
            parent_hash=18436203392999142109,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue1", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=15562446431583779,
            parent_hash=18436203392999142109,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue2", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=13344154764958581569,
            parent_hash=18436203392999142109,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue3", "type:rabbitmq"),
        )


@features.datastreams_monitoring_support_for_rabbitmq_fanout
@scenarios.integrations
class Test_DsmRabbitmq_FanoutExchange:
    """ Verify DSM stats points for RabbitMQ Fanout Exchange"""

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq_fanout_exchange")

    def test_dsm_rabbitmq(self):
        assert self.r.text == "ok"

        DsmHelper.assert_checkpoint_presence(
            hash_=877077567891168935,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestFanoutExchange", "has_routing_key:false", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=6900956252542091373,
            parent_hash=877077567891168935,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue1", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=497609944035068818,
            parent_hash=877077567891168935,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue2", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=15446107644012012909,
            parent_hash=877077567891168935,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue3", "type:rabbitmq"),
        )


@features.datastreams_monitoring_support_for_sqs
@scenarios.integrations
class Test_DsmSQS:
    """ Verify DSM stats points for AWS Sqs Service """

    def setup_dsm_sqs(self):
        self.r = weblog.get("/dsm?integration=sqs&timeout=60", timeout=61)

    def test_dsm_sqs(self):
        assert self.r.text == "ok"

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {
                "producer": 18206246330825886989,
                "consumer": 5236533131035234664,
                "topic": "dsm-system-tests-queue",
            },
            "java": {
                "producer": 16307892913751934142,
                "consumer": 15549836665988044996,
                "topic": "dsm-system-tests-queue-java",
            },
            "default": {
                "producer": 7228682205928812513,
                "consumer": 3767823103515000703,
                "topic": "dsm-system-tests-queue",
            },
        }

        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]
        topic = language_hashes.get(context.library.library, language_hashes.get("default"))["topic"]

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=("direction:out", f"topic:{topic}", "type:sqs"),
        )
        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=("direction:in", f"topic:{topic}", "type:sqs"),
        )


@features.datastreams_monitoring_support_for_sns
@scenarios.integrations
class Test_DsmSNS:
    """ Verify DSM stats points for AWS SNS Service """

    def setup_dsm_sns(self):
        self.r = weblog.get(
            "/dsm?integration=sns&timeout=60&queue=dsm-system-tests-queue-sns&topic=dsm-system-tests-topic-sns",
            timeout=61,
        )

    @missing_feature(library="java", reason="DSM is not implemented for Java AWS SNS.")
    def test_dsm_sns(self):
        assert self.r.text == "ok"

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {"producer": 1231913865272259685, "consumer": 6273982990684090851,},
            "default": {"producer": 5712665980795799642, "consumer": 17643872031898844474,},
        }

        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]
        topic = "arn:aws:sns:us-east-1:000000000000:dsm-system-tests-topic-sns"
        queue = "dsm-system-tests-queue-sns"

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=("direction:out", f"topic:{topic}", "type:sns"),
        )
        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=("direction:in", f"topic:{queue}", "type:sqs"),
        )


@features.datastreams_monitoring_support_for_kinesis
@scenarios.integrations
class Test_DsmKinesis:
    """ Verify DSM stats points for AWS Kinesis Service """

    def setup_dsm_kinesis(self):
        self.r = weblog.get("/dsm?integration=kinesis&timeout=60&stream=dsm-system-tests-stream", timeout=61,)

    @missing_feature(library="java", reason="DSM is not implemented for Java AWS Kinesis.")
    @missing_feature(
        library="python",
        reason="DSM always creates a new pathway on consume, and does not try to read from injected context",
    )
    def test_dsm_kinesis(self):
        assert self.r.text == "ok"

        stream_arn = "arn:aws:kinesis:us-east-1:000000000000:stream/dsm-system-tests-stream"
        stream = "dsm-system-tests-stream"

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {
                "producer": 6740568728215232522,
                "consumer": 13484979344558289202,
                "edge_tags_out": ("direction:out", f"topic:{stream}", "type:kinesis"),
                "edge_tags_in": ("direction:in", f"topic:{stream}", "type:kinesis"),
            },
            "default": {
                "producer": 12766628368524791023,
                "consumer": 17643872031898844474,
                "edge_tags_out": ("direction:out", f"topic:{stream_arn}", "type:kinesis"),
                "edge_tags_in": ("direction:in", f"topic:{stream_arn}", "type:kinesis"),
            },
        }

        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]
        edge_tags_out = language_hashes.get(context.library.library, language_hashes.get("default"))["edge_tags_out"]
        edge_tags_in = language_hashes.get(context.library.library, language_hashes.get("default"))["edge_tags_in"]

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=edge_tags_out,
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in,
        )


@features.datastreams_monitoring_support_for_v1_encoding
@scenarios.integrations
class Test_DsmContext_Extraction_V1:
    """ Verify DSM context is extracted using "dd-pathway-ctx" """

    def setup_dsmcontext_extraction_v1(self):
        queue = "dsm-propagation-test-v1-encoding-queue"
        exchange = "dsm-propagation-test-v1-encoding-exchange"

        # send initial message with v1 pathway context encoding
        assert DsmHelper.produce_rabbitmq_message_v1_propagation(queue, exchange) == "ok"

        self.r = weblog.get(f"/rabbitmq/consume?queue={queue}&exchange={exchange}&timeout=60", timeout=61,)

    @missing_feature(library="java", reason="dd-trace-java cannot extract DSM V1 Byte Headers")
    @missing_feature(library="nodejs", reason="dd-trace-js cannot extract DSM V1 Byte Headers")
    def test_dsmcontext_extraction_v1(self):
        assert "error" not in self.r.text

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {"producer": 9235368231858162135, "consumer": 6273982990684090851,},
            "default": {
                "producer": 9235368231858162135,
                "consumer": 6884439977898629893,
            },  # confirmed that this is correct consumer hash
        }
        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]

        queue = "dsm-propagation-test-v1-encoding-queue"
        edge_tags_in = ("direction:in", f"topic:{queue}", "type:rabbitmq")

        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in,
        )


@features.datastreams_monitoring_support_for_v2_base64_encoding
@scenarios.integrations
class Test_DsmContext_Extraction_V2:
    """ Verify DSM context is extracted using "dd-pathway-ctx/dd-pathway-ctx-base64" """

    def setup_dsmcontext_extraction_v2_base64(self):
        queue = "dsm-propagation-test-v2-encoding-queue"
        exchange = "dsm-propagation-test-v2-encoding-exchange"

        # send initial message with v2 pathway context encoding
        assert DsmHelper.produce_rabbitmq_message_v2_base64_propagation(queue, exchange) == "ok"

        self.r = weblog.get(f"/rabbitmq/consume?queue={queue}&exchange={exchange}&timeout=60", timeout=61,)

    # @missing_feature(library="java", reason="dd-trace-java cannot extract DSM V1 Byte Headers")
    @missing_feature(
        library="nodejs",
        reason="dd-trace-js cannot extract DSM V2 Base64 Headers and throws an error for DSM, never setting checkpoint",
    )
    @missing_feature(library="python", reason="dd-trace-py automatically assumes v1 encoding for rabbitmq")
    def test_dsmcontext_extraction_v2_base64(self):
        assert "error" not in self.r.text

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {"producer": 9235368231858162135, "consumer": 6273982990684090851,},
            "default": {
                "producer": 9235368231858162135,
                "consumer": 6884439977898629893,
            },  # java decodes to consumer hash of 7819692959683983563
        }
        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]

        queue = "dsm-propagation-test-v2-encoding-queue"
        edge_tags_in = ("direction:in", f"topic:{queue}", "type:rabbitmq")

        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in,
        )


@features.datastreams_monitoring_support_for_v1_encoding
@scenarios.integrations
class Test_DsmContext_Injection:
    """ Verify DSM context is injected using correct encoding (base64) """

    def setup_dsmcontext_injection(self):
        queue = "dsm-propagation-test-injection"
        exchange = "dsm-propagation-test-injection-exchange"

        # send initial message with via weblog
        self.r = weblog.get(f"/rabbitmq/produce?queue={queue}&exchange={exchange}&timeout=60", timeout=61,)

        assert self.r.status_code == 200

        # consume message using helper and check propagation type
        self.consume_response = DsmHelper.consume_rabbitmq_injection(queue, exchange, 61)

    # @missing_feature(library="java", reason="dd-trace-java cannot extract DSM V1 Byte Headers")
    # @missing_feature(library="nodejs", reason="dd-trace-js cannot extract DSM V1 Byte Headers")
    def test_dsmcontext_injection(self):
        assert "error" not in self.r.text
        assert "error" not in self.consume_response.text

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {"producer": 9235368231858162135, "consumer": 6273982990684090851,},
            "default": {
                "producer": 9235368231858162135,
                "consumer": 6884439977898629893,
            },  # confirmed that this is correct consumer hash
        }
        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        # consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]

        queue = "dsm-propagation-test-injection"
        edge_tags_out = ("direction:out", f"topic:{queue}", "type:rabbitmq")

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=edge_tags_out,
        )

        print(self.consume_response["result"].properties)
        print(self.consume_response["result"].headers)


class DsmHelper:
    @staticmethod
    def is_tags_included(actual_tags, expected_tags):
        assert isinstance(actual_tags, tuple)
        assert isinstance(expected_tags, tuple)
        for expected_tag in expected_tags:
            if expected_tag not in actual_tags:
                return False
        return True

    @staticmethod
    def assert_checkpoint_presence(hash_, parent_hash, tags):

        assert isinstance(tags, tuple)

        logger.info(f"Look for {hash_}, {parent_hash}, {tags}")

        for data in interfaces.agent.get_dsm_data():
            # some tracers may send separate payloads with stats
            # or backlogs so "Stats" may be empty
            for stats_bucket in data["request"]["content"].get("Stats", {}):
                for stats_point in stats_bucket.get("Stats", {}):
                    observed_hash = stats_point["Hash"]
                    observed_parent_hash = stats_point["ParentHash"]
                    observed_tags = tuple(stats_point["EdgeTags"])

                    logger.info(f"Observed checkpoint: {observed_hash}, {observed_parent_hash}, {observed_tags}")
                    if (
                        observed_hash == hash_
                        and observed_parent_hash == parent_hash
                        and DsmHelper.is_tags_included(observed_tags, tags)
                    ):
                        logger.info("checkpoint found ✅")
                        return

        logger.error("Checkpoint not found 🚨")
        raise ValueError("Checkpoint has not been found, please have a look in logs")

    @staticmethod
    def produce_rabbitmq_message_v1_propagation(queue, exchange):
        # Create a RabbitMQ client
        conn = kombu.Connection("amqp://127.0.0.1:5672")
        conn.connect()
        producer = conn.Producer()

        task_queue = kombu.Queue(queue, kombu.Exchange(exchange), routing_key=queue)

        headers = {
            "dd-pathway-ctx": b"\xd7I\xd5\xcdy\x9e*\x80\xe6\x86\x8a\xa6\xb6c\xe6\x86\x8a\xa6\xb6c"  # encoded V1 pathway from dd-trace-py, pathway hash is: 9235368231858162135
        }
        to_publish = {"message": "DSM Pathway Encoding V1 Test"}

        try:
            producer.publish(
                to_publish,
                exchange=task_queue.exchange,
                routing_key=task_queue.routing_key,
                declare=[task_queue],
                headers=headers,
            )
            logging.info("System Tests RabbitMQ message using V1 DSM Pathway Encoding sent successfully")
            return "ok"
        except Exception as e:
            logging.info(f"Error during DSM RabbitMQ publish message using V1 DSM Pathway Encoding: {e}")
            return "error"

    @staticmethod
    def produce_rabbitmq_message_v2_base64_propagation(queue, exchange):
        # Create a RabbitMQ client
        conn = kombu.Connection("amqp://127.0.0.1:5672")
        conn.connect()
        producer = conn.Producer()

        task_queue = kombu.Queue(queue, kombu.Exchange(exchange), routing_key=queue)

        headers = {
            "dd-pathway-ctx": "10nVzXmeKoCM1uautmOM1uautmM=",  # base64 encoded V2 pathway from dd-trace-py, pathway hash is: 9235368231858162135
            "dd-pathway-ctx-base64": "10nVzXmeKoCM1uautmOM1uautmM=",
        }
        to_publish = {"message": "DSM Pathway Encoding V2 Test"}

        try:
            producer.publish(
                to_publish,
                exchange=task_queue.exchange,
                routing_key=task_queue.routing_key,
                declare=[task_queue],
                headers=headers,
            )
            logging.info("System Tests RabbitMQ message using V2 DSM Pathway Encoding sent successfully")
            return "ok"
        except Exception as e:
            logging.info(f"Error during DSM RabbitMQ publish message using V2 DSM Pathway Encoding: {e}")
            return "error"

    @staticmethod
    def consume_rabbitmq_injection(queue, exchange, timeout):
        # Create a RabbitMQ client
        conn = kombu.Connection("amqp://127.0.0.1:5672")
        task_queue = kombu.Queue(queue, kombu.Exchange(exchange), routing_key=queue)
        messages = []

        def process_message(body, message):
            print(body)
            print(message)
            print(message.body)
            print(message.headers)
            print(message.properties)
            print(message.payload)
            message.ack()
            messages.append(message)

        try:
            with kombu.Consumer(conn, [task_queue], accept=["json"], callbacks=[process_message]):
                conn.drain_events(timeout=timeout)

            if messages:
                logging.info("System Tests RabbitMQ testing injection and consume from weblog successfully")
                return {"result": messages}
            else:
                return {"error": "Message not received"}
        except Exception as e:
            logging.info(f"Error during DSM RabbitMQ publish message using V2 DSM Pathway Encoding: {e}")
            return "error"
