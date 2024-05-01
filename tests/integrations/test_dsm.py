# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, scenarios, irrelevant, context, bug, features, missing_feature, flaky
from utils.tools import logger

import base64
import json
import struct

# Kafka specific
DSM_CONSUMER_GROUP = "testgroup1"

# RabbitMQ Specific
DSM_EXCHANGE = "dsm-system-tests-exchange"
DSM_ROUTING_KEY = "dsm-system-tests-routing-key"

# AWS Kinesis Specific
DSM_STREAM = "dsm-system-tests-stream"

# Generic
DSM_QUEUE = "dsm-system-tests-queue"
DSM_TOPIC = "dsm-system-tests-topic"


@features.datastreams_monitoring_support_for_kafka
@scenarios.integrations
class Test_DsmKafka:
    """ Verify DSM stats points for Kafka """

    def setup_dsm_kafka(self):
        self.r = weblog.get(f"/dsm?integration=kafka&queue={DSM_QUEUE}&group={DSM_CONSUMER_GROUP}")

    @flaky(library="java", reason="AIT-10206")
    def test_dsm_kafka(self):
        assert self.r.text == "ok"

        # Hashes are created by applying the FNV-1 algorithm on
        # checkpoint strings (e.g. service:foo)
        # There is currently no FNV-1 library availble for node.js
        # So we are using a different algorithm for node.js for now
        language_hashes = {
            "nodejs": {"producer": 2931833227331067675, "consumer": 271115008390912609,},
            # we are not using a group consumer for testing go as setup is complex, so no group edge_tag is included in hashing
            "golang": {
                "producer": 4463699290244539355,
                "consumer": 13758451224913876939,
                "edge_tags": ("direction:in", f"topic:{DSM_QUEUE}", "type:kafka"),
            },
            "default": {
                "producer": 4463699290244539355,
                "consumer": 3735318893869752335,
                "edge_tags": ("direction:in", f"group:{DSM_CONSUMER_GROUP}", f"topic:{DSM_QUEUE}", "type:kafka"),
            },
        }

        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]
        edge_tags = language_hashes.get(context.library.library, language_hashes.get("default"))["edge_tags"]

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=("direction:out", f"topic:{DSM_QUEUE}", "type:kafka"),
        )
        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags,
        )


@features.datastreams_monitoring_support_for_http
@scenarios.integrations
class Test_DsmHttp:
    def setup_dsm_http(self):
        # Note that for HTTP, we will still test using Kafka, because the call to Weblog itself is HTTP
        # and will be instrumented as such
        self.r = weblog.get(f"/dsm?integration=kafka&queue={DSM_QUEUE}&group={DSM_CONSUMER_GROUP}")

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
        self.r = weblog.get(
            f"/dsm?integration=rabbitmq&queue={DSM_QUEUE}&exchange={DSM_EXCHANGE}&routing_key={DSM_ROUTING_KEY}"
        )

    @bug(
        library="java",
        reason="Java calculates 16129003365833597547 as producer hash by not using 'routing_key:true' in edge tags.",
    )
    @bug(
        library="dotnet",
        reason="Dotnet calculates 3168906112866048140 as producer hash by using 'routing_key:True' in edge tags, with 'True' capitalized, resulting in different hash.",
    )
    def test_dsm_rabbitmq(self):
        assert self.r.text == "ok"

        # Hashes are created by applying the FNV-1 algorithm on
        # checkpoint strings (e.g. service:foo)
        # There is currently no FNV-1 library availble for node.js
        # So we are using a different algorithm for node.js for now
        language_hashes = {
            "nodejs": {
                "producer": 5246740674878013159,
                "consumer": 10215641161150038469,
                "edge_tags_in": ("direction:in", f"topic:{DSM_ROUTING_KEY}", "type:rabbitmq"),
            },
            "default": {
                "producer": 8945717757344503539,
                "consumer": 247866491670975357,
                "edge_tags_in": ("direction:in", f"topic:{DSM_QUEUE}", "type:rabbitmq"),
                "edge_tags_out": ("direction:out", f"exchange:{DSM_EXCHANGE}", "has_routing_key:true", "type:rabbitmq"),
            },
        }

        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]
        edge_tags_in = language_hashes.get(context.library.library, language_hashes.get("default"))["edge_tags_in"]
        edge_tags_out = language_hashes.get("default")["edge_tags_out"]

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=edge_tags_out,
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in,
        )

    def setup_dsm_rabbitmq_dotnet_legacy(self):
        self.r = weblog.get(
            f"/dsm?integration=rabbitmq&queue={DSM_QUEUE}&exchange={DSM_EXCHANGE}&routing_key={DSM_ROUTING_KEY}"
        )

    @irrelevant(context.library != "dotnet" or context.library > "dotnet@2.33.0", reason="legacy dotnet behavior")
    def test_dsm_rabbitmq_dotnet_legacy(self):
        assert self.r.text == "ok"

        # Dotnet sets the tag for `has_routing_key` to `has_routing_key:True` instead of `has_routing_key:true` like
        # the other tracer libraries, which causes the resulting hash to be different.
        DsmHelper.assert_checkpoint_presence(
            hash_=12547013883960139159,
            parent_hash=0,
            tags=("direction:out", f"exchange:{DSM_EXCHANGE}", "has_routing_key:True", "type:rabbitmq"),
        )

        # There seems to be a bug in dotnet currently where the queue is not passed, causing DSM to default to setting
        # the routing key as the topic.
        # See https://github.com/DataDog/dd-trace-dotnet/blob/6aab5e1b02bec9c9b68a33cd06cc9e7a774f14de/tracer/src/Datadog.Trace/ClrProfiler/AutoInstrumentation/RabbitMQ/RabbitMQIntegration.cs#L144
        # where `queue` is not passed
        DsmHelper.assert_checkpoint_presence(
            hash_=12449081340987959886,
            parent_hash=12547013883960139159,
            tags=("direction:in", f"topic:{DSM_ROUTING_KEY}", "type:rabbitmq"),
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
        self.r = weblog.get(f"/dsm?integration=sqs&timeout=60&queue={DSM_QUEUE}", timeout=61)

    def test_dsm_sqs(self):
        assert self.r.text == "ok"

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {"producer": 18206246330825886989, "consumer": 5236533131035234664, "topic": DSM_QUEUE,},
            "default": {"producer": 7228682205928812513, "consumer": 3767823103515000703, "topic": DSM_QUEUE,},
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
        self.r = weblog.get(f"/dsm?integration=sns&timeout=60&queue={DSM_QUEUE}&topic={DSM_TOPIC}", timeout=61,)

    @missing_feature(library="java", reason="DSM is not implemented for Java AWS SNS.")
    def test_dsm_sns(self):
        assert self.r.text == "ok"

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {"producer": 15583577557400562150, "consumer": 16616233855586708550,},
            "default": {"producer": 5674710414915297150, "consumer": 13847866872847822852,},
        }

        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]
        topic = f"arn:aws:sns:us-east-1:000000000000:{DSM_TOPIC}"

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=("direction:out", f"topic:{topic}", "type:sns"),
        )
        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=("direction:in", f"topic:{DSM_QUEUE}", "type:sqs"),
        )


@features.datastreams_monitoring_support_for_kinesis
@scenarios.integrations
class Test_DsmKinesis:
    """ Verify DSM stats points for AWS Kinesis Service """

    def setup_dsm_kinesis(self):
        self.r = weblog.get(f"/dsm?integration=kinesis&timeout=60&stream={DSM_STREAM}", timeout=61,)

    @missing_feature(library="java", reason="DSM is not implemented for Java AWS Kinesis.")
    def test_dsm_kinesis(self):
        assert self.r.text == "ok"

        stream_arn = f"arn:aws:kinesis:us-east-1:000000000000:stream/{DSM_STREAM}"
        stream = DSM_STREAM

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
                "consumer": 10129046175894237233,
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


@features.datastreams_monitoring_support_context_injection_base64
@scenarios.integrations
class Test_DsmContext_Injection_Base64:
    """ Verify DSM context is injected to carrier using correct encoding (base64) """

    def setup_dsmcontext_injection_base64(self):
        topic = "dsm-injection-topic"
        integration = "kafka"

        self.r = weblog.get(f"/dsm/inject?topic={topic}&integration={integration}", timeout=61,)

    def test_dsmcontext_injection_base64(self):
        assert self.r.status_code == 200

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            "nodejs": {"producer": 18431567370843181989},
            "default": {"producer": 6031446427375485596,},
        }
        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        edge_tags = ("direction:out", f"topic:dsm-injection-topic", "type:kafka")

        # get json carrier object
        carrier = json.loads(self.r.text)

        assert "dd-pathway-ctx-base64" in carrier

        encoded_pathway_b64 = carrier["dd-pathway-ctx-base64"]

        # assert that this is base64
        assert base64.b64encode(base64.b64decode(encoded_pathway_b64)) == bytes(encoded_pathway_b64, "utf-8")

        encoded_pathway = base64.b64decode(bytes(encoded_pathway_b64, "utf-8"))

        # nodejs uses big endian, others use little endian
        _format = "<Q"
        if context.library.library == "nodejs":
            _format = ">Q"
        decoded_pathway = struct.unpack(_format, encoded_pathway[:8])[0]

        assert producer_hash == decoded_pathway

        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash, parent_hash=0, tags=edge_tags,
        )


@features.datastreams_monitoring_support_for_base64_encoding
@scenarios.integrations
class Test_DsmContext_Extraction_Base64:
    """ Verify DSM context is extracted using "dd-pathway-ctx-base64" """

    def setup_dsmcontext_extraction_base64(self):
        topic = "dsm-injection-topic"
        integration = "kafka"

        self.r = weblog.get(
            f"/dsm/extract?topic={topic}&integration={integration}&ctx="
            + '{"dd-pathway-ctx-base64":"nMKD2ZEAtFOy/f/K5mOy/f/K5mM="}',
            timeout=61,
        )

    def test_dsmcontext_extraction_base64(self):
        assert self.r.text == "ok"

        language_hashes = {
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default, also uses routing key since
            # it does not have access to the queue name
            "nodejs": {"producer": 11295735785862509651, "consumer": 18410421833994263340},
            "default": {"producer": 6031446427375485596, "consumer": 12795903374559614717,},
        }
        edge_tags = ("direction:in", f"topic:dsm-injection-topic", "type:kafka")
        producer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["producer"]
        consumer_hash = language_hashes.get(context.library.library, language_hashes.get("default"))["consumer"]

        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags,
        )


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
