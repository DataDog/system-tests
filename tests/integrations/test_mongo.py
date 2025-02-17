# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
from utils import weblog, interfaces, scenarios, features


@features.mongo_support
@scenarios.integrations
class Test_Mongo:
    """Verify that a mongodb span is created"""

    def setup_main(self):
        self.r = weblog.get("/trace/mongo")

    def test_main(self):
        """Verify that a mongodb span has the correct database attributes.
        The command should be {"ping": 1}, on the "admin" database.
        `Ping documentation <https://www.mongodb.com/docs/manual/reference/command/ping/>`_
        """
        spans = [
            s for _, _, s in interfaces.library.get_spans(request=self.r, full_trace=True) if s["type"] == "mongodb"
        ]
        assert len(spans) == 1

        span = spans[0]
        assert json.loads(span["resource"])["operation"] == "ping"

        assert span["meta"]["db.mongodb.collection"] == "1"

        # General database attributes
        assert span["meta"]["db.system"] == "mongodb"
        assert span["meta"]["db.connection_string"] == "mongodb://mongodb:27017"
        assert span["meta"]["db.user"] == "root"
        assert span["meta"]["db.name"] == "admin"
        assert span["meta"]["db.operation"] == "ping"
        assert {"operation": "ping", "database": "admin"}.items() <= json.loads(span["meta"]["db.statement"]).items()
