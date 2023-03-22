# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2023 Datadog, Inc.

from utils import weblog, interfaces, context, bug, missing_feature, scenarios


@missing_feature(condition=context.library != "java", reason="Full Kafka instrumentation only on Java")
@missing_feature(
    context.weblog_variant not in ("spring-boot"),
    reason="The Java /dsm endpoint is only implemented in spring-boot at the moment.",
)
@scenarios.integrations
class Test_DsmKafka:
    """ Verify DSM stats points for Kafka """

    def setup_dsm_kafka(self):
        self.r = weblog.get("/dsm?integration=kafka")

    def test_dsm_kafka(self):
        assert str(self.r.content, "UTF-8") == "ok"
        checkpoints = DsmHelper.parse_dsm_checkpoints(interfaces.agent.get_dsm_data())

        expected_kafka_out = DsmStatsPoint(
            4463699290244539355, 0, ["direction:out", "topic:dsm-system-tests-queue", "type:kafka"]
        )
        expected_kafka_in = DsmStatsPoint(
            3735318893869752335,
            4463699290244539355,
            ["direction:in", "group:testgroup1", "partition:0", "topic:dsm-system-tests-queue", "type:kafka"],
        )

        assert expected_kafka_out in checkpoints
        assert expected_kafka_in in checkpoints


@missing_feature(condition=context.library != "dotnet", reason="Missing partition tag only on dotnet")
@scenarios.integrations
class Test_DsmKafkaNoPartitionTag:
    """ Verify DSM stats points for Kafka """

    def setup_dsm_kafka(self):
        self.r = weblog.get("/dsm?integration=kafka")

    def test_dsm_kafka(self):
        assert str(self.r.content, "UTF-8") == "ok"
        checkpoints = DsmHelper.parse_dsm_checkpoints(interfaces.agent.get_dsm_data())

        expected_kafka_out = DsmStatsPoint(
            4463699290244539355, 0, ["direction:out", "topic:dsm-system-tests-queue", "type:kafka"]
        )
        expected_kafka_in = DsmStatsPoint(
            3735318893869752335,
            4463699290244539355,
            ["direction:in", "group:testgroup1", "topic:dsm-system-tests-queue", "type:kafka"],
        )

        assert expected_kafka_out in checkpoints
        assert expected_kafka_in in checkpoints


@missing_feature(condition=context.library != "java", reason="HTTP instrumentation only on Java")
@missing_feature(
    context.weblog_variant not in ("spring-boot"),
    reason="The Java /dsm endpoint is only implemented in spring-boot at the moment.",
)
@scenarios.integrations
class Test_DsmHttp:
    def setup_dsm_http(self):
        # Note that for HTTP, we will still test using Kafka, because the call to Weblog itself is HTTP
        # and will be instrumented as such
        self.r = weblog.get("/dsm?integration=kafka")

    def test_dsm_http(self):
        assert str(self.r.content, "UTF-8") == "ok"

        checkpoints = DsmHelper.parse_dsm_checkpoints(interfaces.agent.get_dsm_data())
        expected_http = DsmStatsPoint(3883033147046472598, 0, ["direction:in", "type:http"])

        assert expected_http in checkpoints


class DsmHelper:
    @staticmethod
    def parse_dsm_checkpoints(dsm_data):
        checkpoints = set()
        for data in dsm_data:
            for stats_bucket in data["request"]["content"]["Stats"]:
                for stats_point in stats_bucket["Stats"]:
                    point = DsmStatsPoint(stats_point["Hash"], stats_point["ParentHash"], stats_point["EdgeTags"])
                    checkpoints.add(point)
        return checkpoints


class DsmStatsPoint:
    def __init__(self, self_hash, parent_hash, sorted_tags):
        self.self_hash = self_hash
        self.parent_hash = parent_hash
        # Turn input sorted tags into tuples so that it's hashable and order is preserved
        self.sorted_tags = tuple(sorted_tags)

    def __hash__(self):
        return hash((self.self_hash, self.parent_hash, self.sorted_tags))

    def __eq__(self, other):
        return (self.self_hash, self.parent_hash, self.sorted_tags) == (
            other.self_hash,
            other.parent_hash,
            other.sorted_tags,
        )

    def __ne__(self, other):
        # Not strictly necessary, but to avoid having both x==y and x!=y
        # True at the same time
        return not (self == other)

    def __str__(self):
        return (
            "hash: "
            + str(self.self_hash)
            + ", parentHash: "
            + str(self.parent_hash)
            + ", tags: "
            + str(self.sorted_tags)
        )

    def __unicode__(self):
        return (
            "hash: "
            + str(self.self_hash)
            + ", parentHash: "
            + str(self.parent_hash)
            + ", tags: "
            + str(self.sorted_tags)
        )

    def __repr__(self):
        return (
            "hash: "
            + str(self.self_hash)
            + ", parentHash: "
            + str(self.parent_hash)
            + ", tags: "
            + str(self.sorted_tags)
        )
