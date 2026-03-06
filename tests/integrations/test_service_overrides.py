# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features


@features.service_override_source
@scenarios.integrations
class Test_SqlServiceNameSource:
    """Verify that _dd.svc_src is set on SQL spans when the integration overrides the service name"""

    def setup_sql_srv_src(self):
        self.r = weblog.get("/rasp/sqli?user_id=1")

    def test_sql_srv_src(self):
        assert self.r.status_code == 200

        srv_src_found = False
        for _, _, span in interfaces.library.get_spans(request=self.r, full_trace=True):
            if span.get("meta", {}).get("_dd.svc_src"):
                srv_src_found = True
                break

        assert srv_src_found, "Expected at least one SQL span to have _dd.svc_src set"
