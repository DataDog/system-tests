# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, bug, irrelevant, missing_feature
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="?", dotnet="1.28.6", nodejs="?", php="?", python="?", ruby="0.51.0")
class Test_StatusCode(BaseTestCase):
    """ Appsec reports good status code """

    @missing_feature(library="java", reason="response is not reported")
    @bug(library="ruby", reason="status is missing")
    def test_basic(self):
        r = self.weblog_get("/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"})
        assert r.status_code == 404
        interfaces.library.assert_waf_attack(r)

        def check_http_code(event):
            status_code = event["context"]["http"]["response"]["status"]
            assert status_code == 404, f"404 should have been reported, not {status_code}"

            return True

        interfaces.library.add_appsec_validation(r, check_http_code)


@released(golang="1.33.1", nodejs="2.0.0-appsec-alpha.1", php="?", python="?", ruby="0.51.0")
@bug(library="dotnet", reason="request headers are not reported")
class Test_ActorIP(BaseTestCase):
    """ AppSec reports good actor's IP"""

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

    @missing_feature(library="java", reason="actor ip has incorrect data")
    @irrelevant(library="ruby", reason="neither rack or puma provides this info")
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


@released(golang="?", java="0.87.0", nodejs="2.0.0-appsec-alpha.1", php="?", python="?", ruby="0.51.0")
@bug(library="dotnet", reason="none is reported")
class Test_Info(BaseTestCase):
    @bug(library="ruby", reason="name is sinatra io weblog")
    def test_service(self):
        """ Appsec reports the service information """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})

        def _check_service(event):
            name = event["context"]["service"]["name"]
            environment = event["context"]["service"]["environment"]
            assert name == "weblog", f"weblog should have been reported, not {name}"
            assert environment == "system-tests", f"system-tests should have been reported, not {environment}"

            return True

        interfaces.library.add_appsec_validation(r, _check_service)
