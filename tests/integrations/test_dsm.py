# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

import base64
import json
import os

from tests.integrations.utils import compute_dsm_hash

from utils import weblog, interfaces, scenarios, irrelevant, context, bug, features, missing_feature, flaky, logger


# Kafka specific
DSM_CONSUMER_GROUP = "testgroup1"

# RabbitMQ Specific
DSM_EXCHANGE = "dsm-system-tests-exchange"
DSM_ROUTING_KEY = "dsm-system-tests-routing-key"

# AWS Specific
AWS_HOST = os.getenv("SYSTEM_TESTS_AWS_URL", "")

# TO DO CHECK RUNNER ENV FOR A SYSTEM TESTS AWS ENV INDICATING IF AWS TESTS IS LOCAL OR REMOTE

# If the AWS host points to localstack, we are using local AWS mocking, else assume the real account
LOCAL_AWS_ACCT = "000000000000"  # if 'localstack' in AWS_HOST else "601427279990"
AWS_ACCT = LOCAL_AWS_ACCT  # if 'localstack' in AWS_HOST else "601427279990"
AWS_TESTING = "local" if LOCAL_AWS_ACCT == AWS_ACCT else "remote"

# AWS Kinesis Specific
DSM_STREAM = "dsm-system-tests-stream"

# Generic
DSM_QUEUE = "dsm-system-tests-queue"

DSM_QUEUE_SQS = "dsm-system-tests-queue"
DSM_QUEUE_SNS = "dsm-system-tests-sns-queue"
DSM_TOPIC = "dsm-system-tests-topic"

# Queue requests can take a while, so give time for them to complete
DSM_REQUEST_TIMEOUT = 61


WEBLOG_VARIANT_SANITIZED = context.weblog_variant.replace(".", "_").replace(" ", "_").replace("/", "_")


def get_message(test, system):
    return f"[test_dsm.py::{test}] [{system.upper()}] Hello from {context.library.name} DSM test: {scenarios.integrations_aws.unique_id}"


@features.datastreams_monitoring_support_for_kafka
@scenarios.integrations
class Test_DsmKafka:
    """Verify DSM stats points for Kafka"""

    def setup_dsm_kafka(self):
        self.r = weblog.get(f"/dsm?integration=kafka&queue={DSM_QUEUE}&group={DSM_CONSUMER_GROUP}")

    @bug(context.library == "python" and context.weblog_variant in ("flask-poc", "uds-flask"), reason="APMAPI-1058")
    @irrelevant(library="nodejs", reason="fixing node hashing")
    @irrelevant(context.library in ["java", "dotnet"], reason="New behavior with cluster id not merged yet.")
    def test_dsm_kafka(self):
        assert self.r.text == "ok"

        # Hashes are created by applying the FNV-1 algorithm on
        # checkpoint strings (e.g. service:foo)
        # There is currently no FNV-1 library availble for node.js
        # So we are using a different algorithm for node.js for now
        if context.library == "nodejs":
            producer_hash = 8001907834230501985
            consumer_hash = 12353223394116417855
        elif context.library == "golang":
            producer_hash = 4463699290244539355
            consumer_hash = 13758451224913876939
        else:
            producer_hash = 14216899112169674443
            consumer_hash = 4247242616665718048

        if context.library == "golang":
            # we are not using a group consumer for testing go as setup is complex, so no group edge_tag is included in hashing
            edge_tags_in: tuple = ("direction:in", f"topic:{DSM_QUEUE}", "type:kafka")
            edge_tags_out: tuple = ("direction:out", f"topic:{DSM_QUEUE}", "type:kafka")
        else:
            edge_tags_in: tuple = (
                "direction:in",
                f"group:{DSM_CONSUMER_GROUP}",
                "kafka_cluster_id:5L6g3nShT-eMCtK--X86sw",
                f"topic:{DSM_QUEUE}",
                "type:kafka",
            )
            edge_tags_out: tuple = (
                "direction:out",
                "kafka_cluster_id:5L6g3nShT-eMCtK--X86sw",
                f"topic:{DSM_QUEUE}",
                "type:kafka",
            )

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=0, tags=edge_tags_out)
        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in)

    def setup_dsm_kafka_without_cluster_id(self):
        self.r = weblog.get(f"/dsm?integration=kafka&queue={DSM_QUEUE}&group={DSM_CONSUMER_GROUP}")

    @features.datastreams_monitoring_support_for_kafka
    @irrelevant(library="nodejs", reason="fixing node hashing")
    @irrelevant(context.library != "dotnet")
    def test_dsm_kafka_without_cluster_id(self):
        assert self.r.text == "ok"

        producer_hash = 4463699290244539355
        consumer_hash = 3735318893869752335

        edge_tags_in: tuple = ("direction:in", f"group:{DSM_CONSUMER_GROUP}", f"topic:{DSM_QUEUE}", "type:kafka")
        edge_tags_out: tuple = ("direction:out", f"topic:{DSM_QUEUE}", "type:kafka")

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=0, tags=edge_tags_out)
        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in)


@features.datastreams_monitoring_support_for_http
@scenarios.integrations
class Test_DsmHttp:
    def setup_dsm_http(self):
        # Note that for HTTP, we will still test using Kafka, because the call to Weblog itself is HTTP
        # and will be instrumented as such
        self.r = weblog.get(
            f"/dsm?integration=kafka&queue={DSM_QUEUE}&group={DSM_CONSUMER_GROUP}", timeout=DSM_REQUEST_TIMEOUT
        )

    def test_dsm_http(self):
        assert self.r.text == "ok"

        DsmHelper.assert_checkpoint_presence(
            hash_=3883033147046472598, parent_hash=0, tags=("direction:in", "type:http")
        )


@features.datastreams_monitoring_support_for_rabbitmq
@scenarios.integrations
class Test_DsmRabbitmq:
    """Verify DSM stats points for RabbitMQ"""

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get(
            f"/dsm?integration=rabbitmq&queue={DSM_QUEUE}&exchange={DSM_EXCHANGE}&routing_key={DSM_ROUTING_KEY}",
            timeout=DSM_REQUEST_TIMEOUT,
        )

    @bug(library="java", reason="APMAPI-840")
    @flaky(library="python", reason="APMAPI-724")
    @missing_feature(context.library <= "nodejs@5.24.0")
    @irrelevant(library="nodejs", reason="fixing node hashing")
    def test_dsm_rabbitmq(self):
        assert self.r.text == "ok"

        # Hashes are created by applying the FNV-1 algorithm on
        # checkpoint strings (e.g. service:foo)
        # There is currently no FNV-1 library availble for node.js
        # So we are using a different algorithm for node.js for now
        if context.library == "nodejs":
            producer_hash = 16680966241789857864
            consumer_hash = 7235406874724180592
        else:
            producer_hash = 8945717757344503539
            consumer_hash = 247866491670975357

        edge_tags_in = ("direction:in", f"topic:{DSM_QUEUE}", "type:rabbitmq")
        edge_tags_out = ("direction:out", f"exchange:{DSM_EXCHANGE}", "has_routing_key:true", "type:rabbitmq")

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=0, tags=edge_tags_out)
        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in)

    def setup_dsm_rabbitmq_dotnet_legacy(self):
        self.r = weblog.get(
            f"/dsm?integration=rabbitmq&queue={DSM_QUEUE}&exchange={DSM_EXCHANGE}&routing_key={DSM_ROUTING_KEY}",
            timeout=DSM_REQUEST_TIMEOUT,
        )

    @irrelevant(context.library != "dotnet" or context.library > "dotnet@2.33.0", reason="legacy dotnet behavior")
    @irrelevant(library="nodejs", reason="fixing node hashing")
    def test_dsm_rabbitmq_dotnet_legacy(self):
        assert self.r.text == "ok"

        # .NET sets the tag for `has_routing_key` to `has_routing_key:True` instead of `has_routing_key:true` like
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
    """Verify DSM stats points for RabbitMQ Topic Exchange"""

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq_topic_exchange", timeout=DSM_REQUEST_TIMEOUT)

    @bug(library="java", reason="APMAPI-840")
    @irrelevant(library="nodejs", reason="fixing node hashing")
    def test_dsm_rabbitmq(self):
        assert self.r.text == "ok"

        parent_hash = 14115675228093516275
        DsmHelper.assert_checkpoint_presence(
            hash_=parent_hash,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestTopicExchange", "has_routing_key:true", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=17456221739323133462,
            parent_hash=parent_hash,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue1", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=6709599110187021152,
            parent_hash=parent_hash,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue2", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=4518514625593640902,
            parent_hash=parent_hash,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue3", "type:rabbitmq"),
        )


@features.datastreams_monitoring_support_for_rabbitmq_fanout
@scenarios.integrations
class Test_DsmRabbitmq_FanoutExchange:
    """Verify DSM stats points for RabbitMQ Fanout Exchange"""

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq_fanout_exchange", timeout=DSM_REQUEST_TIMEOUT)

    @bug(library="java", reason="APMAPI-840")
    def test_dsm_rabbitmq(self):
        assert self.r.text == "ok"

        parent_hash = 528013466165804625

        DsmHelper.assert_checkpoint_presence(
            hash_=parent_hash,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestFanoutExchange", "has_routing_key:false", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=1551162056316679489,
            parent_hash=parent_hash,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue1", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=5919279740143028634,
            parent_hash=parent_hash,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue2", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=10096313447786601025,
            parent_hash=parent_hash,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue3", "type:rabbitmq"),
        )


@features.datastreams_monitoring_support_for_sqs
@scenarios.integrations_aws
class Test_DsmSQS:
    """Verify DSM stats points for AWS Sqs Service"""

    def setup_dsm_sqs(self):
        message = get_message("Test_DsmSQS", "sqs")

        # we can't add the time hash to node since we can't replicate the hashing algo in python and compute a hash,
        # which changes for each run with the time stamp added
        if context.library.name != "nodejs":
            self.queue = (
                f"{DSM_QUEUE}_{context.library.name}_{WEBLOG_VARIANT_SANITIZED}_{scenarios.integrations_aws.unique_id}"
            )
        else:
            self.queue = f"{DSM_QUEUE}_{context.library.name}"

        self.r = weblog.get(
            f"/dsm?integration=sqs&timeout=60&queue={self.queue}&message={message}", timeout=DSM_REQUEST_TIMEOUT
        )

    @irrelevant(library="nodejs", reason="fixing node hashing")
    def test_dsm_sqs(self):
        assert self.r.text == "ok"

        tags_out = ("direction:out", f"topic:{self.queue}", "type:sqs")
        tags_in = ("direction:in", f"topic:{self.queue}", "type:sqs")

        if context.library == "nodejs":
            producer_hash = 2649573563161019048
            consumer_hash = 3674518247845931278
        else:
            producer_hash = compute_dsm_hash(0, tags_out)
            consumer_hash = compute_dsm_hash(producer_hash, tags_in)

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=0, tags=tags_out)
        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=tags_in)


@features.datastreams_monitoring_support_for_sns
@scenarios.integrations_aws
class Test_DsmSNS:
    """Verify DSM stats points for AWS SNS Service"""

    def setup_dsm_sns(self):
        message = get_message("Test_DsmSNS", "sns")

        # we can't add the time hash to node since we can't replicate the hashing algo in python and compute a hash,
        # which changes for each run with the time stamp added
        if context.library.name != "nodejs":
            self.topic = f"{DSM_TOPIC}_{context.library.name}_{WEBLOG_VARIANT_SANITIZED}_{scenarios.integrations_aws.unique_id}_raw"
            self.queue = f"{DSM_QUEUE_SNS}_{context.library.name}_{WEBLOG_VARIANT_SANITIZED}_{scenarios.integrations_aws.unique_id}_raw"
        else:
            self.topic = f"{DSM_TOPIC}_{context.library.name}_raw"
            self.queue = f"{DSM_QUEUE_SNS}_{context.library.name}_raw"

        self.r = weblog.get(
            f"/dsm?integration=sns&timeout=60&queue={self.queue}&topic={self.topic}&message={message}",
            timeout=DSM_REQUEST_TIMEOUT,
        )

    @irrelevant(library="nodejs", reason="fixing node hashing")
    def test_dsm_sns(self):
        assert self.r.text == "ok"

        arn = f"arn:aws:sns:us-east-1:{AWS_ACCT}:{self.topic}"
        topic = self.topic if context.library in ["java", "dotnet"] else arn

        if context.library == "nodejs":
            producer_hash = 15466202493380574985 if AWS_TESTING == "remote" else 4474403991591098370
            consumer_hash = 9372735371403270535 if AWS_TESTING == "remote" else 3839681565914825635
            tags_out = ("direction:out", f"topic:{topic}", "type:sns")
            tags_in = ("direction:in", f"topic:{self.queue}", "type:sqs")
        else:
            tags_out = ("direction:out", f"topic:{topic}", "type:sns")
            tags_in = ("direction:in", f"topic:{self.queue}", "type:sqs")
            producer_hash = compute_dsm_hash(0, tags_out)
            consumer_hash = compute_dsm_hash(producer_hash, tags_in)

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=0, tags=tags_out)
        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=tags_in)


@features.datastreams_monitoring_support_for_kinesis
@scenarios.integrations_aws
class Test_DsmKinesis:
    """Verify DSM stats points for AWS Kinesis Service"""

    def setup_dsm_kinesis(self):
        message = get_message("Test_DsmKinesis", "kinesis")

        # we can't add the time hash to node since we can't replicate the hashing algo in python and compute a hash,
        # which changes for each run with the time stamp added
        if context.library.name != "nodejs":
            self.stream = (
                f"{DSM_STREAM}_{context.library.name}_{WEBLOG_VARIANT_SANITIZED}_{scenarios.integrations_aws.unique_id}"
            )
        else:
            self.stream = f"{DSM_STREAM}_{context.library.name}"

        self.r = weblog.get(
            f"/dsm?integration=kinesis&timeout=60&stream={self.stream}&message={message}",
            timeout=DSM_REQUEST_TIMEOUT,
        )

    @missing_feature(library="java", reason="DSM is not implemented for Java AWS Kinesis.")
    @irrelevant(library="nodejs", reason="fixing node hashing")
    def test_dsm_kinesis(self):
        assert self.r.text == "ok"

        stream_arn = f"arn:aws:kinesis:us-east-1:{AWS_ACCT}:stream/{self.stream}"

        if context.library == "nodejs":
            tags_out = ("direction:out", f"topic:{self.stream}", "type:kinesis")
            tags_in = ("direction:in", f"topic:{self.stream}", "type:kinesis")
            producer_hash = 6996061165171108813
            consumer_hash = 18286084103800622023
        else:
            tags_out = ("direction:out", f"topic:{stream_arn}", "type:kinesis")
            tags_in = ("direction:in", f"topic:{stream_arn}", "type:kinesis")
            producer_hash = compute_dsm_hash(0, tags_out)
            consumer_hash = compute_dsm_hash(producer_hash, tags_in)

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=0, tags=tags_out)
        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=tags_in)


@features.datastreams_monitoring_support_context_injection_base64
@scenarios.integrations
class Test_DsmContext_Injection_Base64:
    """Verify DSM context is injected to carrier using correct encoding (base64)"""

    def setup_dsmcontext_injection_base64(self):
        topic = "dsm-injection-topic"
        integration = "kafka"

        self.r = weblog.get(f"/dsm/inject?topic={topic}&integration={integration}", timeout=DSM_REQUEST_TIMEOUT)

    @irrelevant(library="nodejs", reason="fixing node hashing")
    def test_dsmcontext_injection_base64(self):
        assert self.r.status_code == 200

        if context.library == "nodejs":
            producer_hash = 11949115791662959359
        else:
            producer_hash = 6031446427375485596

        edge_tags = ("direction:out", "topic:dsm-injection-topic", "type:kafka")

        # get json carrier object
        carrier = json.loads(self.r.text)

        assert "dd-pathway-ctx-base64" in carrier

        encoded_pathway_b64 = carrier["dd-pathway-ctx-base64"]

        # assert that this is base64
        assert base64.b64encode(base64.b64decode(encoded_pathway_b64)) == bytes(encoded_pathway_b64, "utf-8")

        base64.b64decode(bytes(encoded_pathway_b64, "utf-8"))

        # nodejs uses big endian, others use little endian
        _format = "<Q"
        if context.library == "nodejs":
            _format = ">Q"
        # decoded_pathway = struct.unpack(_format, encoded_pathway[:8])[0]

        # assert producer_hash == decoded_pathway

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=0, tags=edge_tags)


@features.datastreams_monitoring_support_for_base64_encoding
@scenarios.integrations
class Test_DsmContext_Extraction_Base64:
    """Verify DSM context is extracted using dd-pathway-ctx-base64"""

    def setup_dsmcontext_extraction_base64(self):
        topic = "dsm-injection-topic"
        integration = "kafka"

        ctx = {"dd-pathway-ctx-base64": "nMKD2ZEAtFOy/f/K5mOy/f/K5mM="}

        self.r = weblog.get(
            f"/dsm/extract?topic={topic}&integration={integration}&ctx="
            + json.dumps(ctx),  # GoP2wpyqhGvWhsLZ5mPqhsLZ5mM= for java :(, nMKD2ZEAtFOSrODZ5mOSrODZ5mM= for go,
            timeout=DSM_REQUEST_TIMEOUT,
        )

    @irrelevant(library="nodejs", reason="fixing node hashing")
    def test_dsmcontext_extraction_base64(self):
        assert self.r.text == "ok"

        if context.library == "nodejs":
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default, also uses routing key since
            # it does not have access to the queue name
            consumer_hash = 3232267919319990015
            producer_hash = 6031446427375485596
        else:
            consumer_hash = 12795903374559614717
            producer_hash = 6031446427375485596

        edge_tags = ("direction:in", "topic:dsm-injection-topic", "type:kafka")

        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags)


@features.datastreams_monitoring_support_for_manual_checkpoints
@scenarios.integrations
class Test_Dsm_Manual_Checkpoint_Intra_Process:
    """Verify DSM stats points for manual checkpoints within the same process thread"""

    def setup_dsm_manual_checkpoint_intra_process(self):
        self.produce = weblog.get(
            "/dsm/manual/produce?type=dd-streams&target=system-tests-queue", timeout=DSM_REQUEST_TIMEOUT
        )
        headers = {}
        headers["_datadog"] = json.dumps(
            {"dd-pathway-ctx-base64": self.produce.headers.get("dd-pathway-ctx-base64", "")}
        )
        self.consume = weblog.get(
            "/dsm/manual/consume?type=dd-streams&source=system-tests-queue",
            headers=headers,
            timeout=DSM_REQUEST_TIMEOUT,
        )

    @irrelevant(library="nodejs", reason="Node.js doesn't sort the DSM edge tags and has different hashes.")
    def test_dsm_manual_checkpoint_intra_process(self):
        assert self.produce.status_code == 200
        assert self.produce.text == "ok"
        assert "dd-pathway-ctx-base64" in self.produce.headers

        assert self.consume.status_code == 200
        assert self.consume.text == "ok"

        if context.library == "nodejs":
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            producer_hash = 9931057434765374197
            consumer_hash = 17324614250411467957
            parent_producer_hash = 0
        elif context.library == "java":
            # for some reason, Java assigns earlier HTTP in checkpoint as parent
            # Parent HTTP Checkpoint: 3883033147046472598, 0, ('direction:in', 'type:http')
            producer_hash = 1538441441403845096
            consumer_hash = 17074055019471758954
            parent_producer_hash = 3883033147046472598
        else:
            producer_hash = 2925617884093644655
            consumer_hash = 9012955179260244489
            parent_producer_hash = 0

        edge_tags_out: tuple
        edge_tags_in: tuple
        if context.library == "java":
            edge_tags_out = ("direction:out", "topic:system-tests-queue", "type:dd-streams")
            edge_tags_in = ("direction:in", "topic:system-tests-queue", "type:dd-streams")
        else:
            edge_tags_out = (
                "direction:out",
                "manual_checkpoint:true",
                "topic:system-tests-queue",
                "type:dd-streams",
            )
            edge_tags_in = (
                "direction:in",
                "manual_checkpoint:true",
                "topic:system-tests-queue",
                "type:dd-streams",
            )

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=parent_producer_hash, tags=edge_tags_out)
        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in)


@features.datastreams_monitoring_support_for_manual_checkpoints
@scenarios.integrations
class Test_Dsm_Manual_Checkpoint_Inter_Process:
    """Verify DSM stats points for manual checkpoints across threads"""

    def setup_dsm_manual_checkpoint_inter_process(self):
        self.produce_threaded = weblog.get(
            "/dsm/manual/produce_with_thread?type=dd-streams-threaded&target=system-tests-queue",
            timeout=DSM_REQUEST_TIMEOUT,
        )
        headers = {}
        headers["_datadog"] = json.dumps(
            {"dd-pathway-ctx-base64": self.produce_threaded.headers.get("dd-pathway-ctx-base64", "")}
        )
        self.consume_threaded = weblog.get(
            "/dsm/manual/consume_with_thread?type=dd-streams-threaded&source=system-tests-queue",
            headers=headers,
            timeout=DSM_REQUEST_TIMEOUT,
        )

    @irrelevant(library="nodejs", reason="Node.js doesn't sort the DSM edge tags and has different hashes.")
    def test_dsm_manual_checkpoint_inter_process(self):
        assert self.produce_threaded.status_code == 200
        assert self.produce_threaded.text == "ok"
        assert "dd-pathway-ctx-base64" in self.produce_threaded.headers

        assert self.consume_threaded.status_code == 200
        assert self.consume_threaded.text == "ok"

        if context.library == "nodejs":
            # nodejs uses a different hashing algorithm and therefore has different hashes than the default
            producer_hash = 12899996614288916469
            consumer_hash = 4416193018187534291
            parent_producer_hash = 0
        elif context.library == "java":
            producer_hash = 4667583249035065277
            consumer_hash = 2161125765733997838
            parent_producer_hash = 3883033147046472598
        else:
            producer_hash = 11970957519616335697
            consumer_hash = 14397921880946757763
            parent_producer_hash = 0

        edge_tags_out: tuple
        edge_tags_in: tuple

        if context.library == "java":
            # for some reason, Java assigns earlier HTTP in checkpoint as parent
            # Parent HTTP Checkpoint: 3883033147046472598, 0, ('direction:in', 'type:http')
            edge_tags_out = ("direction:out", "topic:system-tests-queue", "type:dd-streams-threaded")
            edge_tags_in = ("direction:in", "topic:system-tests-queue", "type:dd-streams-threaded")
        else:
            edge_tags_out = (
                "direction:out",
                "manual_checkpoint:true",
                "topic:system-tests-queue",
                "type:dd-streams-threaded",
            )
            edge_tags_in = (
                "direction:in",
                "manual_checkpoint:true",
                "topic:system-tests-queue",
                "type:dd-streams-threaded",
            )

        DsmHelper.assert_checkpoint_presence(hash_=producer_hash, parent_hash=parent_producer_hash, tags=edge_tags_out)
        DsmHelper.assert_checkpoint_presence(hash_=consumer_hash, parent_hash=producer_hash, tags=edge_tags_in)


class DsmHelper:
    @staticmethod
    def is_tags_included(actual_tags, expected_tags) -> bool:
        assert isinstance(actual_tags, tuple)
        assert isinstance(expected_tags, tuple)

        return all(expected_tag in actual_tags for expected_tag in expected_tags)

    @staticmethod
    def assert_checkpoint_presence(hash_, parent_hash, tags) -> None:
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
