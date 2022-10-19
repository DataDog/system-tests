# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import pytest

from tests.constants import PYTHON_RELEASE_GA_1_1, PYTHON_RELEASE_PUBLIC_BETA
from utils import BaseTestCase, context, coverage, interfaces, irrelevant, released, rfc, bug

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")

@released(
    dotnet="2.13.0",
    golang="1.39.0",
    java="0.107.1",
    nodejs="3.2.0",
    php="0.76.0",
    python=PYTHON_RELEASE_GA_1_1,
    ruby="?",
)
@coverage.basic
class Test_StandardTagsClientIp(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.client_ip tags"""

    def test_is_reported(self):
        headers = {"X-Cluster-Client-IP": "10.42.42.42, 43.43.43.43, fe80::1"}
        r = self.weblog_get("/waf/", headers=headers)

        tags = {
            "http.client_ip": "43.43.43.43",
            "http.headers.x-cluster-client-ip": "43.43.43.43",
        }
        interfaces.library.add_span_tag_validation(request=r, tags=tags)

    def test_is_not_reported(self):
        # TODO
