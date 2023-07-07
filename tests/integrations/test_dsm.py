# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, scenarios, released, context
from utils.tools import logger

@released(cpp="?", golang="?", php="?", python="?", ruby="?")
@released(dotnet="2.29.0")
@released(java={"spring-boot": "1.13.0", "*": "?"})
@released(nodejs="4.4.0")
@scenarios.integrations
class Test_DsmKafka:
    """ Verify DSM stats points for Kafka """

    def setup_dsm_kafka(self):
        self.r = weblog.get("/dsm?integration=kafka")

    def test_dsm_kafka(self):
        assert self.r.text == "ok"

        if context.library == "nodejs":
            consumer_hash = 2931833227331067675
            producer_hash = 8618469865309575104
        else:
            consumer_hash = 4463699290244539355
            producer_hash = 16645700936287432977

        DsmHelper.assert_checkpoint_presence(
            hash_=consumer_hash, parent_hash=0, tags=("direction:out", "topic:dsm-system-tests-queue", "type:kafka"),
        )
        DsmHelper.assert_checkpoint_presence(
            hash_=producer_hash,
            parent_hash=consumer_hash,
            tags=("direction:in", "group:testgroup2", "topic:dsm-system-tests-queue", "type:kafka"),
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
