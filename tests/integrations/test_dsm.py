# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, scenarios, released, irrelevant, context, bug
from utils.tools import logger


@released(cpp="?", golang="?", php="?", python="?", ruby="?")
@released(dotnet="2.29.0")
@released(java={"spring-boot": "1.13.0", "*": "?"})
@released(nodejs="4.4.0")
@scenarios.integrations
class Test_DsmKafka:
    """ Verify DSM stats points for Kafka """

    def setup_dsm_kafka(self):
        # Hashes are created by applying the FNV-1 algorithm on
        # checkpoint strings (e.g. service:foo)
        # There is currently no FNV-1 library availble for node.js
        # So we are using a different algorithm for node.js for now
        if context.library == "nodejs":
            self.consumer_hash = 2931833227331067675
            self.producer_hash = 271115008390912609
        else:
            self.consumer_hash = 4463699290244539355
            self.producer_hash = 3735318893869752335

        # Requests to this endpoint in Node sometimes timeout with the default.
        request_timeout = 10

        self.r = weblog.get("/dsm?integration=kafka", timeout=request_timeout)
        if self.r.status_code == 200:
            DsmHelper.wait_for_hashes((self.consumer_hash, self.producer_hash))

    def test_dsm_kafka(self):
        assert (self.r.status_code, self.r.text) == (200, "ok")
        DsmHelper.assert_checkpoint_presence(
            hash_=self.consumer_hash,
            parent_hash=0,
            tags=("direction:out", "topic:dsm-system-tests-queue", "type:kafka"),
        )
        DsmHelper.assert_checkpoint_presence(
            hash_=self.producer_hash,
            parent_hash=self.consumer_hash,
            tags=("direction:in", "group:testgroup1", "topic:dsm-system-tests-queue", "type:kafka"),
        )


@released(cpp="?", dotnet="?", golang="?", nodejs="?", php="?", python="?", ruby="?")
@released(java={"spring-boot": "1.12.1", "*": "?"})
@scenarios.integrations
class Test_DsmHttp:
    def setup_dsm_http(self):
        # Note that for HTTP, we will still test using Kafka, because the call to Weblog itself is HTTP
        # and will be instrumented as such
        self.r = weblog.get("/dsm?integration=kafka")
        self.hash_ = 3883033147046472598
        if self.r.status_code == 200:
            DsmHelper.wait_for_hashes((self.hash_,))

    def test_dsm_http(self):
        assert (self.r.status_code, self.r.text) == (200, "ok")
        DsmHelper.assert_checkpoint_presence(hash_=self.hash_, parent_hash=0, tags=("direction:in", "type:http"))


@released(cpp="?", golang="?", nodejs="?", php="?", python="?", ruby="?")
@released(java={"spring-boot": "1.13.0", "*": "?"})
@released(dotnet="2.29.0")
@scenarios.integrations
class Test_DsmRabbitmq:
    """ Verify DSM stats points for RabbitMQ """

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq")
        self.hash_out = 6176024609184775446
        self.hash_in = 1648106384315938543
        if self.r.status_code == 200:
            DsmHelper.wait_for_hashes((self.hash_out, self.hash_in))

    @bug(library="dotnet", reason="bug in dotnet behavior")
    def test_dsm_rabbitmq(self):
        assert (self.r.status_code, self.r.text) == (200, "ok")
        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_out,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestDirectExchange", "has_routing_key:true", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_in,
            parent_hash=self.hash_out,
            tags=("direction:in", "topic:systemTestRabbitmqQueue", "type:rabbitmq"),
        )

    def setup_dsm_rabbitmq_dotnet_legacy(self):
        self.r = weblog.get("/dsm?integration=rabbitmq")
        self.hash_out_dotnet = 12547013883960139159
        self.hash_in_dotnet = 12449081340987959886
        if self.r.status_code == 200:
            DsmHelper.wait_for_hashes((self.hash_out_dotnet, self.hash_in_dotnet))

    @irrelevant(context.library != "dotnet" or context.library > "dotnet@2.33.0", reason="legacy dotnet behavior")
    def test_dsm_rabbitmq_dotnet_legacy(self):
        assert self.r.text == "ok"

        # Dotnet sets the tag for `has_routing_key` to `has_routing_key:True` instead of `has_routing_key:true` like
        # the other tracer libraries, which causes the resulting hash to be different.
        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_out_dotnet,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestDirectExchange", "has_routing_key:True", "type:rabbitmq"),
        )

        # There seems to be a bug in dotnet currently where the queue is not passed, causing DSM to default to setting
        # the routing key as the topic.
        # See https://github.com/DataDog/dd-trace-dotnet/blob/6aab5e1b02bec9c9b68a33cd06cc9e7a774f14de/tracer/src/Datadog.Trace/ClrProfiler/AutoInstrumentation/RabbitMQ/RabbitMQIntegration.cs#L144
        # where `queue` is not passed
        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_in_dotnet,
            parent_hash=self.hash_out_dotnet,
            tags=("direction:in", "topic:testRoutingKey", "type:rabbitmq"),
        )


@released(cpp="?", dotnet="?", golang="?", nodejs="?", php="?", python="?", ruby="?")
@released(java={"spring-boot": "1.13.0", "*": "?"})
@scenarios.integrations
class Test_DsmRabbitmq_TopicExchange:
    """ Verify DSM stats points for RabbitMQ Topic Exchange"""

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq_topic_exchange")
        self.hash_out = 18436203392999142109
        self.hash_in_1 = 11364757106893616177
        self.hash_in_2 = 15562446431583779
        self.hash_in_3 = 13344154764958581569
        if self.r.status_code == 200:
            DsmHelper.wait_for_hashes((self.hash_out, self.hash_in_1, self.hash_in_2, self.hash_in_3))

    def test_dsm_rabbitmq(self):
        assert (self.r.status_code, self.r.text) == (200, "ok")
        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_out,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestTopicExchange", "has_routing_key:true", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_in_1,
            parent_hash=self.hash_out,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue1", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_in_2,
            parent_hash=self.hash_out,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue2", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_in_3,
            parent_hash=self.hash_out,
            tags=("direction:in", "topic:systemTestRabbitmqTopicQueue3", "type:rabbitmq"),
        )


@released(cpp="?", dotnet="?", golang="?", nodejs="?", php="?", python="?", ruby="?")
@released(java={"spring-boot": "1.13.0", "*": "?"})
@scenarios.integrations
class Test_DsmRabbitmq_FanoutExchange:
    """ Verify DSM stats points for RabbitMQ Fanout Exchange"""

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq_fanout_exchange")
        self.hash_out = 877077567891168935
        self.hash_in_1 = 6900956252542091373
        self.hash_in_2 = 497609944035068818
        self.hash_in_3 = 15446107644012012909
        if self.r.status_code == 200:
            DsmHelper.wait_for_hashes((self.hash_out, self.hash_in_1, self.hash_in_2, self.hash_in_3))

    def test_dsm_rabbitmq(self):
        assert (self.r.status_code, self.r.text) == (200, "ok")
        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_out,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestFanoutExchange", "has_routing_key:false", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_in_1,
            parent_hash=self.hash_out,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue1", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_in_2,
            parent_hash=self.hash_out,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue2", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=self.hash_in_3,
            parent_hash=self.hash_out,
            tags=("direction:in", "topic:systemTestRabbitmqFanoutQueue3", "type:rabbitmq"),
        )


class DsmHelper:
    @staticmethod
    def wait_for_hashes(hashes):
        from utils import wait_conditions

        if isinstance(hashes, int):
            hashes = (hashes,)
        for hash_ in hashes:

            wait_conditions.add(timeout=40, condition=lambda: DsmHelper.check_checkpoint_by_hash(hash_))

    @staticmethod
    def assert_checkpoint_presence(hash_, parent_hash, tags):

        assert isinstance(tags, tuple)

        logger.info(f"Look for {hash_}, {parent_hash}, {tags}")

        for data in interfaces.agent.get_dsm_data():
            for stats_bucket in data["request"]["content"]["Stats"]:
                for stats_point in stats_bucket["Stats"]:
                    observed_hash = stats_point["Hash"]
                    observed_parent_hash = stats_point["ParentHash"]
                    observed_tags = tuple(stats_point["EdgeTags"])

                    logger.debug(f"Observed checkpoint: {observed_hash}, {observed_parent_hash}, {observed_tags}")
                    if observed_hash == hash_ and observed_parent_hash == parent_hash and observed_tags == tags:
                        logger.info("checkpoint found ✅")
                        return

        logger.error("Checkpoint not found 🚨")
        raise ValueError("Checkpoint has not been found, please have a look in logs")

    @staticmethod
    def check_checkpoint_by_hash(hash_):
        for data in interfaces.agent.get_dsm_data():
            for stats_bucket in data["request"]["content"]["Stats"]:
                for stats_point in stats_bucket["Stats"]:
                    observed_hash = stats_point["Hash"]
                    if observed_hash == hash_:
                        return True
        return False
