# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, skipif


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
@skipif(context.library == "java", reason="missing feature: response is not reported")
class Test_StatusCode(BaseTestCase):
    def test_basic(self):
        """ Appsec reports good status code """
        r = self.weblog_get("/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"})
        assert r.status_code == 404
        interfaces.library.assert_waf_attack(r)

        def check_http_code(event):
            status_code = event["context"]["http"]["response"]["status"]
            assert status_code == 404, f"404 should have been reported, not {status_code}"

            return True

        interfaces.library.add_appsec_validation(r, check_http_code)


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
@skipif(context.library == "dotnet", reason="missing feature: request headers are not reported")
class Test_ActorIP(BaseTestCase):
    def test_http_remote_ip(self):
        """ AppSec reports the HTTP request peer IP. """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1",}, stream=True)
        actual_remote_ip = r.raw._connection.sock.getsockname()[0]
        r.close()

        def _check_remote_ip(event):
            remote_ip = event["context"]["http"]["request"]["remote_ip"]
            assert remote_ip == actual_remote_ip, f"request remote ip should be {actual_remote_ip}"

            return True

        interfaces.library.add_appsec_validation(r, _check_remote_ip)

    def test_http_request_headers(self):
        """ AppSec reports the HTTP headers used for actor IP detection."""
        r = self.weblog_get(
            "/waf/",
            headers={
                "X-Forwarded-For": "42.42.42.42, 43.43.43.43",
                "X-Client-IP": "42.42.42.42, 43.43.43.43",
                "X-Real-IP": "42.42.42.42, 43.43.43.43",
                "X-Forwarded": "42.42.42.42, 43.43.43.43",
                "X-Cluster-Client-IP": "42.42.42.42, 43.43.43.43",
                "Forwarded-For": "42.42.42.42, 43.43.43.43",
                "Forwarded": "42.42.42.42, 43.43.43.43",
                "Via": "42.42.42.42, 43.43.43.43",
                "True-Client-IP": "42.42.42.42, 43.43.43.43",
                "User-Agent": "Arachni/v1",
            },
        )

        def _check_header_is_present(header_name):
            def inner_check(event):
                assert header_name.lower() in [
                    n.lower() for n in event["context"]["http"]["request"]["headers"].keys()
                ], f"header {header_name} not reported"

                return True

            return inner_check

        interfaces.library.add_appsec_validation(r, _check_header_is_present("x-forwarded-for"))
        interfaces.library.add_appsec_validation(r, _check_header_is_present("x-client-ip"))
        interfaces.library.add_appsec_validation(r, _check_header_is_present("x-real-ip"))
        interfaces.library.add_appsec_validation(r, _check_header_is_present("x-forwarded"))
        interfaces.library.add_appsec_validation(r, _check_header_is_present("x-cluster-client-ip"))
        interfaces.library.add_appsec_validation(r, _check_header_is_present("forwarded-for"))
        interfaces.library.add_appsec_validation(r, _check_header_is_present("forwarded"))
        interfaces.library.add_appsec_validation(r, _check_header_is_present("via"))
        interfaces.library.add_appsec_validation(r, _check_header_is_present("true-client-ip"))

    @skipif(context.library == "java", reason="missing feature: actor ip has incorrect data")
    def test_actor_ip(self):
        """ AppSec reports the correct actor ip. """
        r = self.weblog_get(
            "/waf/", headers={"X-Cluster-Client-IP": "10.42.42.42, 43.43.43.43, fe80::1", "User-Agent": "Arachni/v1",},
        )

        def _check_actor_ip(event):
            if "actor" in event["context"]:
                actor_ip = event["context"]["actor"]["ip"]["address"]

                assert actor_ip == "43.43.43.43", "actor IP should be 43.43.43.43"

            return True

        interfaces.library.add_appsec_validation(r, _check_actor_ip)
