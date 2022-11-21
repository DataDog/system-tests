# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, released


@released(cpp="?", golang="?", java="?", dotnet="?", nodejs="?", php="?", ruby="?")
@missing_feature(context.library == "python" and context.weblog_variant != "flask-poc", reason="Missing on weblog")
class Test_Dbm(BaseTestCase):
    """Verify behavior of DBM propagation"""

    def test_trace_payload(self):
        def validator(span):
            if span.get("span_type") != "sql":
                return

            meta = span.get("meta", {})
            assert "_dd.dbm_trace_injected" in meta

            return True

        r = self.weblog_get("/dbm", params={"url": "http://weblog:7777"})
        interfaces.library.add_assertion(r.status_code == 200)
        interfaces.library.add_span_validation(request=r, validator=validator)

    def test_dbm_payload(self):
        # TODO: Add schema for validation of dbm payload agent/backend
        # TODO: Add check for dbm payload agent/backend ensure that the expected trace data
        pass
