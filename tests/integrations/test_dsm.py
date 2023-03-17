# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, context, bug, missing_feature, scenarios


@missing_feature(condition=context.library != "java", reason="Endpoint is not implemented on weblog")
@scenarios.dsm
class Test_Dsm:
    """ Verify that a cassandra span is created """

    def setup_main(self):
        print("setting up dsm test")
        self.r = weblog.get("/dsm")

    def test_main(self):
        assert(str(self.r.content, 'UTF-8') == "ok")

        checkpoints = interfaces.agent.get_dsm_checkpoints1(self.r)
        print(checkpoints)
        points_set = set()
        for data in checkpoints:
            for stats_bucket in data["request"]["content"]["Stats"]:
                for stats_point in stats_bucket["Stats"]:
                    point = DsmStatsPoint(stats_point["Hash"], stats_point["ParentHash"], stats_point["EdgeTags"])
                    points_set.add(point)

        expected_stats_point1 = DsmStatsPoint(3883033147046472598, 0, ['direction:in', 'type:http'])
        expected_stats_point2 = DsmStatsPoint(4463699290244539355, 0, ['direction:out', 'topic:dsm-system-tests-queue', 'type:kafka'])
        expected_stats_point3 = DsmStatsPoint(3735318893869752335, 4463699290244539355, ['direction:in', 'group:testgroup1', 'partition:0', 'topic:dsm-system-tests-queue', 'type:kafka'])

        assert(len(points_set) == 3)
        assert(expected_stats_point1 in points_set)
        assert(expected_stats_point2 in points_set)
        assert(expected_stats_point3 in points_set)

class DsmStatsPoint:
    def __init__(self, self_hash, parent_hash, sorted_tags):
        self.self_hash = self_hash
        self.parent_hash = parent_hash
        # Turn input sorted tags into tuples so that it's hashable and order is preserved
        self.sorted_tags = tuple(sorted_tags)

    def __hash__(self):
        return hash((self.self_hash, self.parent_hash, self.sorted_tags))

    def __eq__(self, other):
        return (self.self_hash, self.parent_hash, self.sorted_tags) == (other.self_hash, other.parent_hash, other.sorted_tags)

    def __ne__(self, other):
        # Not strictly necessary, but to avoid having both x==y and x!=y
        # True at the same time
        return not(self == other)

    def __str__(self):
        return "hash: " + str(self.self_hash) + ", parentHash: " + str(self.parent_hash) + ", tags: " + str(self.sorted_tags)
    def __unicode__(self):
        return "hash: " + str(self.self_hash) + ", parentHash: " + str(self.parent_hash) + ", tags: " + str(self.sorted_tags)
    def __repr__(self):
        return "hash: " + str(self.self_hash) + ", parentHash: " + str(self.parent_hash) + ", tags: " + str(self.sorted_tags)