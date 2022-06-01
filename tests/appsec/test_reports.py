# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, coverage, interfaces, released, bug, coverage, missing_feature, flaky, rfc
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(dotnet="1.28.6", java="0.92.0", nodejs="2.0.0", php_appsec="0.1.0", python="1.1.0rc2.dev")
@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@bug(library="python@1.1.0", reason="a PR was not included in the release")
@coverage.basic
class Test_StatusCode(BaseTestCase):
    """ Appsec reports good status code """

    def test_basic(self):
        r = self.weblog_get("/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"})
        assert r.status_code == 404
        interfaces.library.assert_waf_attack(r)

        def check_http_code_legacy(event):
            status_code = event["context"]["http"]["response"]["status"]
            assert status_code == 404, f"404 should have been reported, not {status_code}"

            return True

        def check_http_code(span, appsec_data):
            status_code = span["meta"]["http.status_code"]
            assert status_code == "404", f"404 should have been reported, not {status_code}"

            return True

        interfaces.library.add_appsec_validation(r, validator=check_http_code, legacy_validator=check_http_code_legacy)


@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@released(dotnet="1.30.0", java="0.98.1", nodejs="2.0.0", php_appsec="0.3.0", python="?")
@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
@coverage.good
class Test_ActorIP(BaseTestCase):
    """ AppSec reports good actor's IP"""

    def test_http_remote_ip(self):
        """ AppSec reports the HTTP request peer IP. """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1",}, stream=True)
        actual_remote_ip = r.raw._connection.sock.getsockname()[0]
        r.close()

        def legacy_validator(event):
            remote_ip = event["context"]["http"]["request"]["remote_ip"]
            assert remote_ip == actual_remote_ip, f"request remote ip should be {actual_remote_ip}"

            return True

        def validator(span, appsec_data):
            ip = span["meta"]["network.client.ip"]
            assert ip == actual_remote_ip, f"network.client.ip should be {actual_remote_ip}"

            return True

        interfaces.library.add_appsec_validation(r, validator=validator, legacy_validator=legacy_validator)

    @missing_feature(library="golang", reason="Not clear if it must be done on backend side. Waiting for clarification")
    @missing_feature(library="nodejs", reason="Not clear if it must be done on backend side. Waiting for clarification")
    @missing_feature(library="ruby", reason="Not clear if it must be done on backend side. Waiting for clarification")
    def test_actor_ip(self):
        """ AppSec reports the correct actor ip. """

        headers = {"X-Cluster-Client-IP": "10.42.42.42, 43.43.43.43, fe80::1", "User-Agent": "Arachni/v1"}
        r = self.weblog_get("/waf/", headers=headers)

        def legacy_validator(event):
            assert "actor" in event["context"], "actor is missing from context"
            actor_ip = event["context"]["actor"]["ip"]["address"]
            assert actor_ip == "43.43.43.43", f"actor should be 43.43.43.43, not {actor_ip}"

            return True

        def validator(span, appsec_data):
            assert "actor.ip" in span["meta"], "actor.ip is missing from in meta tags"
            actor_ip = span["meta"]["actor.ip"]
            assert actor_ip == "43.43.43.43", f"actor.ip should be 43.43.43.43, not {actor_ip}"

            return True

        interfaces.library.add_appsec_validation(r, validator=validator, legacy_validator=legacy_validator)


@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@released(dotnet="2.0.0", java="0.87.0", nodejs="2.0.0", php="0.68.2", python="1.1.0rc2.dev")
@flaky(context.library <= "php@0.68.2")
@bug(library="python@1.1.0", reason="a PR was not included in the release")
@coverage.good
class Test_Info(BaseTestCase):
    """ Environment (production, staging) from DD_ENV variable """

    def test_service(self):
        """ Appsec reports the service information """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})

        def _check_service_legacy(event):
            name = event["context"]["service"]["name"]
            environment = event["context"]["service"]["environment"]
            assert name == "weblog", f"weblog should have been reported, not {name}"
            assert environment == "system-tests", f"system-tests should have been reported, not {environment}"

            return True

        def _check_service(span, appsec_data):
            name = span.get("service")
            environment = span.get("meta", {}).get("env")
            assert name == "weblog", f"weblog should have been reported, not {name}"
            assert environment == "system-tests", f"system-tests should have been reported, not {environment}"

            return True

        interfaces.library.add_appsec_validation(r, legacy_validator=_check_service_legacy, validator=_check_service)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2186870984/HTTP+header+collection")
@released(
    golang="1.37.0"
    if context.weblog_variant == "gin"
    else "1.36.0"
    if context.weblog_variant in ["echo", "chi"]
    else "1.34.0"
)
@released(dotnet="1.30.0", nodejs="2.0.0", php_appsec="0.2.0", python="1.1.0rc2.dev")
@missing_feature(context.library == "ruby" and context.libddwaf_version is None)
@bug(library="python@1.1.0", reason="a PR was not included in the release")
@coverage.good
class Test_RequestHeaders(BaseTestCase):
    """ Request Headers for IP resolution """

    @bug(context.library < "dotnet@2.1.0")
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

        interfaces.library.add_appsec_reported_header(r, "x-forwarded-for")
        interfaces.library.add_appsec_reported_header(r, "x-client-ip")
        interfaces.library.add_appsec_reported_header(r, "x-real-ip")
        interfaces.library.add_appsec_reported_header(r, "x-forwarded")
        interfaces.library.add_appsec_reported_header(r, "x-cluster-client-ip")
        interfaces.library.add_appsec_reported_header(r, "forwarded-for")
        interfaces.library.add_appsec_reported_header(r, "forwarded")
        interfaces.library.add_appsec_reported_header(r, "via")
        interfaces.library.add_appsec_reported_header(r, "true-client-ip")


@coverage.basic
class Test_TagsFromRule(BaseTestCase):
    """ Tags (Category & event type) from the rule """

    def test_basic(self):
        """ attack timestamp is given by start property of span """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})

        def validator(span, appsec_data):
            for trigger in appsec_data["triggers"]:
                assert "rule" in trigger
                assert "tags" in trigger["rule"]
                assert "type" in trigger["rule"]["tags"]
                assert "category" in trigger["rule"]["tags"]

        interfaces.library.add_appsec_validation(r, validator=validator, is_success_on_expiry=True)


@coverage.basic
class Test_AttackTimestamp(BaseTestCase):
    """ Attack timestamp """

    def test_basic(self):
        """ attack timestamp is given by start property of span """
        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})

        def validator(span, appsec_data):
            assert "start" in span, "span should contain start property"
            assert isinstance(span["start"], int), f"start property should an int, not {repr(span['start'])}"

        interfaces.library.add_appsec_validation(r, validator=validator, is_success_on_expiry=True)
