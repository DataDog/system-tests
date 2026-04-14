# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features


@features.mongo_support
@scenarios.integrations
class Test_Mongo:
    """Verify that a mongodb span is created"""

    def setup_main(self):
        self.r = weblog.get("/trace/mongo")

    def test_main(self):
        # PHP uses "mongodb" (Type::MONGO = 'mongodb'); other tracers use "mongo"
        for _, _, span in interfaces.library.get_spans(request=self.r):
            if span.get("type") in ("mongo", "mongodb"):
                return
        raise ValueError(f"No mongo/mongodb trace found for request {self.r.get_rid()}")
