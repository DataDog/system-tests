# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc, context





@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
class Test_API10_request_headers:
    """Shell Injection through query parameters"""

    def setup_api10_get_headers(self):
        self.r = weblog.get("/external_request", params={"user-agent": "system-tests-agent"})

    def test_api10_get_headers(self):
        assert self.r.status_code == 200
