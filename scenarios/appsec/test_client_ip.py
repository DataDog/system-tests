# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

import pytest

from tests.constants import PYTHON_RELEASE_GA_1_1, PYTHON_RELEASE_PUBLIC_BETA
from utils import BaseTestCase, context, coverage, interfaces, irrelevant, released, rfc, bug

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(dotnet="?", golang="?", java="?")
@released(nodejs="3.6.0", php="?", python="?", ruby="?")
@coverage.basic
class Test_StandardTagsClientIp(BaseTestCase):
    """Tests to verify that libraries annotate spans with correct http.client_ip tags"""

    def test_not_reported(self):
        """Test IP-related span tags are not reported when ASM is disabled"""

        def validator(span):
            meta = span.get("meta", {})
            assert "appsec.event" not in meta, "unexpected appsec event while appsec should be disabled"
            assert "http.client_ip" not in meta, "unexpected http.client_ip tag"
            assert "network.client.ip" not in meta, "unexpected network.client.ip tag"
            assert (
                "http.request.headers.x-cluster-client-ip" not in meta
            ), "unexpected http.request.headers.x-cluster-client-ip tag"

            return True

        headers = {
            "X-Cluster-Client-IP": "10.42.42.42, 43.43.43.43, fe80::1",
            "User-Agent": "Arachni/v1",
        }
        r = self.weblog_get("/waf/", headers=headers)

        interfaces.library.add_span_validation(request=r, validator=validator)
