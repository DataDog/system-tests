# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, scenarios, released
from utils.tools import logger


@released(cpp="?", golang="?", nodejs="?", php="?", python="?", ruby="?")
@released(dotnet="2.29.0")
@released(java={"spring-boot": "1.13.0", "*": "?"})
@scenarios.integrations
class Test_DsmKafka:
    """ Verify DSM stats points for Kafka """

    def setup_dsm_kafka(self):
        self.r = weblog.get("/dsm?integration=kafka")

    def test_dsm_kafka(self):
        assert self.r.text == "ok"

        DsmHelper.assert_checkpoint_presence(
            hash_=4463699290244539355,
            parent_hash=0,
            tags=("direction:out", "topic:dsm-system-tests-queue", "type:kafka"),
        )
        DsmHelper.assert_checkpoint_presence(
            hash_=3735318893869752335,
            parent_hash=4463699290244539355,
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

    def test_dsm_http(self):
        assert self.r.text == "ok"

        DsmHelper.assert_checkpoint_presence(
            hash_=3883033147046472598, parent_hash=0, tags=("direction:in", "type:http")
        )


@released(cpp="?", dotnet="?", golang="?", nodejs="?", php="?", python="?", ruby="?")
@released(java={"spring-boot": "1.13.0", "*": "?"})
@scenarios.integrations
class Test_DsmRabbitmq:
    """ Verify DSM stats points for RabbitMQ """

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq")

    def test_dsm_rabbitmq(self):
        assert self.r.text == "ok"

        DsmHelper.assert_checkpoint_presence(
            hash_=6176024609184775446,
            parent_hash=0,
            tags=("direction:out", "exchange:systemTestDirectExchange", "has_routing_key:true", "type:rabbitmq"),
        )

        DsmHelper.assert_checkpoint_presence(
            hash_=1648106384315938543,
            parent_hash=6176024609184775446,
            tags=("direction:in", "topic:systemTestRabbitmqQueue", "type:rabbitmq"),
        )


@released(cpp="?", golang="?", nodejs="?", php="?", python="?", ruby="?", java="?")
@released(dotnet="2.29.0")
@scenarios.integrations
class Test_DsmRabbitmq_Dotnet:
    """ Verify DSM stats points for RabbitMQ, specifically for Dotnet """

    def setup_dsm_rabbitmq(self):
        self.r = weblog.get("/dsm?integration=rabbitmq")

    def test_dsm_rabbitmq(self):
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


class DsmHelper:
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
