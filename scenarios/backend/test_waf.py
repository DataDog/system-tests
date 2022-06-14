# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import pytest

from utils import context, coverage, BaseTestCase, interfaces, irrelevant, released

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(dotnet="?", golang="?", java="?", nodejs="", php="0.75.0", python="?", ruby="?")
@coverage.basic
class Test_Basic(BaseTestCase):
    """ Basic tests on waf backend """

    def test_basic(self):
        """ Send a basic attack, and check that backend tags it as an attack """
        r = self.weblog_get("/.git/config")
        interfaces.library.assert_no_appsec_event(r)
        interfaces.backend.assert_waf_attack(r)
