# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, scenario


@scenario("APPSEC_UNSUPPORTED")
class TestAppSecDeactivated:
    def setup_no_attack_detected(self):
        self.r1 = weblog.get("/", headers={"User-Agent": "Arachni/v1"})
        self.r2 = weblog.get("/waf", params={"attack": "<script>"})

    def test_no_attack_detected(self):
        """Appsec does not catch any attack"""
        interfaces.library.assert_no_appsec_event(self.r1)
        interfaces.library.assert_no_appsec_event(self.r2)

    def test_unsupported_logs_present(self):
        pass  # TODO have a solid way to read logs
        # f = open("/app/logs/docker/weblog.log", "r")
        # logs = f.read()
        # assert "AppSec could not start because the current environment is not supported." in logs
