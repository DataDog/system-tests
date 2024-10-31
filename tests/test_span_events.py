# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, weblog, interfaces, features


@scenarios.agent_not_supporting_span_events
class Test_Backend:
    """Misc test around agent/backend communication"""

    def test_good_backend(self):
        """Agent reads and use DD_SITE env var"""
        interfaces.agent.assert_use_domain(context.dd_site)
