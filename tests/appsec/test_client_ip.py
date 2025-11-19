# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, scenarios, features


@scenarios.everything_disabled
@features.appsec_standard_tags_client_ip
class Test_StandardTagsClientIp:
    """Tests to verify that libraries annotate spans with correct http.client_ip tags"""

    def setup_not_reported(self):
        headers = {
            "X-Cluster-Client-IP": "10.42.42.42, 43.43.43.43, fe80::1",
            "User-Agent": "Arachni/v1",
        }

        self.r = weblog.get("/waf/", headers=headers)

    def test_not_reported(self):
        """Test IP-related span tags are not reported when ASM is disabled"""

        def validator(span: dict):
            meta = span.get("meta", {})
            assert "appsec.event" not in meta, "unexpected appsec event while appsec should be disabled"
            assert "http.client_ip" not in meta, "unexpected http.client_ip tag"
            assert "network.client.ip" not in meta, "unexpected network.client.ip tag"
            assert (
                "http.request.headers.x-cluster-client-ip" not in meta
            ), "unexpected http.request.headers.x-cluster-client-ip tag"

            return True

        interfaces.library.validate_one_span(request=self.r, validator=validator)
