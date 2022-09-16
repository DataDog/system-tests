# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import pytest
from tests.constants import PYTHON_RELEASE_PUBLIC_BETA, PYTHON_RELEASE_GA_1_1
from utils import BaseTestCase, bug, context, coverage, interfaces, irrelevant, missing_feature, released, rfc

if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")

RUNTIME_FAMILIES = ["nodejs", "ruby", "jvm", "dotnet", "go", "php", "python"]


@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.36.0")
@released(dotnet="1.29.0", java="0.92.0", python="1.1.0rc2.dev")
@released(nodejs="2.0.0", php_appsec="0.1.0", ruby="0.54.2")
@bug(library="python@1.1.0", reason="a PR was not included in the release")
@coverage.good
class Test_RetainTraces(BaseTestCase):
    """ Retain trace (manual keep & appsec.event = true) """

    @classmethod
    def setup_class(cls):
        """Send a bunch of attack, to be sure that something is done on AppSec side"""
        get = cls().weblog_get

        get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160
        get("/waf", headers={"random-key": "acunetix-user-agreement"})  # rules.security_scanner.crs_913_110

    def test_appsec_event_span_tags(self):
        """
        Spans with AppSec events should have the general AppSec span tags, along with the appsec.event and
        _sampling_priority_v1 tags
        """

        def validate_appsec_event_span_tags(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if "appsec.event" not in span["meta"]:
                raise Exception("Can't find appsec.event in span's meta")

            if span["meta"]["appsec.event"] != "true":
                raise Exception(f'appsec.event in span\'s meta should be "true", not {span["meta"]["appsec.event"]}')

            if "_sampling_priority_v1" not in span["metrics"]:
                raise Exception("Metric _sampling_priority_v1 should be set on traces that are manually kept")

            MANUAL_KEEP = 2
            if span["metrics"]["_sampling_priority_v1"] != MANUAL_KEEP:
                raise Exception(f"Trace id {span['trace_id']} , sampling priority should be {MANUAL_KEEP}")

            return True

        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.add_span_validation(r, validate_appsec_event_span_tags)


@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.36.0")
@released(dotnet="1.29.0", java="0.104.0", nodejs="2.0.0")
@released(php_appsec="0.1.0", python="0.58.5", ruby="0.54.2")
@coverage.good
class Test_AppSecEventSpanTags(BaseTestCase):
    """ AppSec correctly fill span tags. """

    @classmethod
    def setup_class(cls):
        """Send a bunch of attack, to be sure that something is done on AppSec side"""
        get = cls().weblog_get

        get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160
        get("/waf", headers={"random-key": "acunetix-user-agreement"})  # rules.security_scanner.crs_913_110

    def test_custom_span_tags(self):
        """AppSec should store in all APM spans some tags when enabled."""

        def validate_custom_span_tags(span):
            if span.get("type") != "web":
                return

            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if "_dd.appsec.enabled" not in span["metrics"]:
                raise Exception("Can't find _dd.appsec.enabled in span's metrics")

            if "_dd.runtime_family" not in span["meta"]:
                raise Exception("Can't find _dd.runtime_family in span's meta")

            if span["metrics"]["_dd.appsec.enabled"] != 1:
                raise Exception(
                    f'_dd.appsec.enabled in span\'s metrics should be 1 or 1.0, not {span["metrics"]["_dd.appsec.enabled"]}'
                )

            if span["meta"]["_dd.runtime_family"] not in RUNTIME_FAMILIES:
                raise Exception(f"_dd.runtime_family {span['_dd.runtime_family']}, should be in {RUNTIME_FAMILIES}")

            return True

        interfaces.library.add_span_validation(validator=validate_custom_span_tags)

    @bug(context.library < PYTHON_RELEASE_GA_1_1, reason="a PR was not included in the release")
    @irrelevant(context.library not in ["golang", "nodejs", "java", "dotnet"], reason="test")
    def test_header_collection(self):
        """
        AppSec should collect some headers for http.request and http.response and store them in span tags.
        Note that this test checks for collection, not data.
        """

        def assertHeaderInSpanMeta(span, h):
            if h not in span["meta"]:
                raise Exception("Can't find {header} in span's meta".format(header=h))

        def validate_request_headers(span):
            for h in ["user-agent", "host", "content-type"]:
                assertHeaderInSpanMeta(span, f"http.request.headers.{h}")
            return True

        def validate_response_headers(span):
            for h in ["content-type", "content-length", "content-language"]:
                assertHeaderInSpanMeta(span, f"http.response.headers.{h}")
            return True

        r = self.weblog_get("/headers", headers={"User-Agent": "Arachni/v1", "Content-Type": "text/plain"})
        interfaces.library.add_span_validation(r, validate_request_headers)
        interfaces.library.add_span_validation(r, validate_response_headers)

    @bug(context.library < "java@0.93.0")
    def test_root_span_coherence(self):
        """Appsec tags are not on span where type is not web"""

        def validator(span):
            if (
                span.get("type") not in ["web", "http", "rpc"]
                and "metrics" in span
                and "_dd.appsec.enabled" in span["metrics"]
            ):
                raise Exception("_dd.appsec.enabled should be present only when span type is web")

            if (
                span.get("type") not in ["web", "http", "rpc"]
                and "meta" in span
                and "_dd.runtime_family" in span["meta"]
            ):
                raise Exception("_dd.runtime_family should be present only when span type is web")

            return True

        interfaces.library.add_span_validation(validator=validator)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2365948382/Sensitive+Data+Obfuscation")
@released(golang="1.38.0", dotnet="2.7.0", java="?", nodejs="2.6.0", php_appsec="0.3.0", python=PYTHON_RELEASE_GA_1_1, ruby="?")
@coverage.good
class Test_AppSecObfuscator(BaseTestCase):
    """AppSec obfuscates sensitive data."""

    def test_appsec_obfuscator_key(self):
        """General obfuscation test of several attacks on several rule addresses."""
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.
        SECRET = "this is a very secret value having the attack"

        def validate_appsec_span_tags(span, appsec_data):
            if SECRET in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            return True

        r = self.weblog_get(
            "/waf/",
            headers={"Http-Api-Token": f"{SECRET} acunetix-product"},
            params={"pwd": f"{SECRET} select pg_sleep"},
        )
        interfaces.library.assert_waf_attack(r, address="server.request.headers.no_cookies")
        interfaces.library.assert_waf_attack(r, address="server.request.query")
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)

    @irrelevant(context.appsec_rules_version >= "1.2.7", reason="cookies were disabled for the time being")
    def test_appsec_obfuscator_cookies(self):
        """
        Specific obfuscation test for the cookies which often contain sensitive data and are
        expected to be properly obfuscated on sensitive cookies only.
        """
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.
        SECRET_VALUE_WITH_SENSITIVE_KEY = "this is a very sensitive cookie value having the .htaccess attack"
        SECRET_VALUE_WITH_NON_SENSITIVE_KEY = "not a sensitive cookie value having an select pg_sleep attack"

        def validate_appsec_span_tags(span, appsec_data):
            if SECRET_VALUE_WITH_SENSITIVE_KEY in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            if SECRET_VALUE_WITH_NON_SENSITIVE_KEY not in span["meta"]["_dd.appsec.json"]:
                raise Exception("Could not find the non-sensitive cookie data")
            return True

        r = self.weblog_get(
            "/waf/", cookies={"Bearer": SECRET_VALUE_WITH_SENSITIVE_KEY, "Good": SECRET_VALUE_WITH_NON_SENSITIVE_KEY}
        )
        interfaces.library.assert_waf_attack(r, address="server.request.cookies")
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)

    def test_appsec_obfuscator_value(self):
        """Obfuscation test of a matching rule parameter value containing a sensitive keyword."""
        # Validate that the AppSec event do not contain the following secret value.
        SECRET = "BEARER lwqjedqwdoqwidmoqwndun32i"
        # The following payload will be sent as a raw encoded string via the request params
        # and matches an XSS attack. It contains an access token secret we shouldn't have in the event.
        sensitive_raw_payload = r"""{
            "activeTab":"39612314-1890-45f7-8075-c793325c1d70",'
            "allOpenTabs":["132ef2e5-afaa-4e20-bc64-db9b13230a","39612314-1890-45f7-8075-c793325c1d70"],
            "lastPage":{
                "accessToken":"BEARER lwqjedqwdoqwidmoqwndun32i",
                "account":{
                    "name":"F123123",
                    "contactCustomFields":{
                        "ffa77959-1ff3-464b-a3af-e5410e436f1f":{
                            "questionServiceEntityType":"CustomField",
                            "question":{
                                "code":"Manager Name",
                                "questionTypeInfo":{
                                    "questionType":"OpenEndedText",
                                    "answerFormatType":"General"
                                    ,"scores":[]
                                },
                                "additionalInfo":{
                                    "codeSnippetValue":"<script>alert(xss)</script>"
                                }
                            }
                        }
                    }
                }
            }"""

        def validate_appsec_span_tags(span, appsec_data):
            if SECRET in span["meta"]["_dd.appsec.json"]:
                raise Exception("The security events contain the secret value that should be obfuscated")
            return True

        r = self.weblog_get(
            "/waf/",
            headers={"my-header": f"password={SECRET} acunetix-product"},
            params={"payload": sensitive_raw_payload},
        )
        interfaces.library.assert_waf_attack(r, address="server.request.headers.no_cookies")
        interfaces.library.assert_waf_attack(r, address="server.request.query")
        interfaces.library.add_appsec_validation(r, validate_appsec_span_tags)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2186870984/HTTP+header+collection")
@released(dotnet="2.5.1", php_appsec="0.2.2", python=PYTHON_RELEASE_PUBLIC_BETA, ruby="1.0.0.beta1")
@released(golang="1.37.0" if context.weblog_variant == "gin" else "1.36.2")
@released(nodejs="2.0.0", java="0.102.0")
@coverage.good
class Test_CollectRespondHeaders(BaseTestCase):
    """ AppSec should collect some headers for http.response and store them in span tags. """

    def test_header_collection(self):
        def assertHeaderInSpanMeta(span, h):
            if h not in span["meta"]:
                raise Exception("Can't find {header} in span's meta".format(header=h))

        def validate_response_headers(span):
            for h in ["content-type", "content-length", "content-language"]:
                assertHeaderInSpanMeta(span, f"http.response.headers.{h}")
            return True

        r = self.weblog_get("/headers", headers={"User-Agent": "Arachni/v1", "Content-Type": "text/plain"})
        interfaces.library.add_span_validation(r, validate_response_headers)


@coverage.not_implemented
class Test_DistributedTraceInfo:
    """ Distributed traces info (Services, URL, trace id) """
