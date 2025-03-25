# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, weblog, interfaces, features, missing_feature


@features.unix_domain_sockets_support_for_traces
class Test_Backend:
    """Misc test around agent/backend communication"""

    def test_good_backend(self):
        """Agent reads and use DD_SITE env var"""
        interfaces.agent.assert_use_domain(context.dd_site)


@features.unix_domain_sockets_support_for_traces
class Test_Library:
    """Misc test around library/agent communication"""

    def setup_receive_request_trace(self):
        self.r = weblog.get("/")

    @missing_feature(library="cpp_httpd", reason="For some reason, span type is server i/o web")
    def test_receive_request_trace(self):
        """Basic test to verify that libraries sent traces to the agent"""
        interfaces.library.assert_receive_request_root_trace()
