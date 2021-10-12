# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, BaseTestCase, interfaces, skipif


class Test_Backend(BaseTestCase):
    """Misc test around agent/backend communication"""

    def test_good_backend(self):
        """Agent reads and use DD_SITE env var"""
        interfaces.agent.assert_use_domain(context.dd_site)


@skipif(context.weblog_variant == "echo-poc", reason="not relevant: echo isn't instrumented")
class Test_Library(BaseTestCase):
    """Misc test around library/agent communication"""

    def test_receive_request_trace(self):
        """Basic test to verify that libraries sent traces to the agent"""
        r = self.weblog_get("/")
        assert r.status_code == 200
        interfaces.library.assert_receive_request_root_trace()
