# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils.dd_constants import PYTHON_RELEASE_GA_1_1
from utils import weblog, bug, context, interfaces, irrelevant, rfc, missing_feature, scenarios, features
from utils.tools import nested_lookup


RUNTIME_FAMILIES = ["nodejs", "ruby", "jvm", "dotnet", "go", "php", "python"]


@bug(context.library == "python@1.1.0", reason="APMRP-360")
@features.security_events_metadata
class Test_RetainTraces:
    """Retain trace (manual keep & appsec.event = true)"""

    def setup_appsec_event_span_tags(self):
        """Send a bunch of attack, to be sure that something is done on AppSec side"""

        weblog.get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160
        weblog.get("/waf", headers={"random-key": "acunetix-user-agreement"})  # rules.security_scanner.crs_913_110

        self.r = weblog.get("/waf/", headers={"User-Agent": "Arachni/v1"})

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

        interfaces.library.validate_spans(self.r, validate_appsec_event_span_tags)


@features.security_events_metadata
class Test_AppSecEventSpanTags:
    """AppSec correctly fill span tags."""

    def setup_custom_span_tags(self):
        weblog.get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160
        weblog.get("/waf", headers={"random-key": "acunetix-user-agreement"})  # rules.security_scanner.crs_913_110

    def test_custom_span_tags(self):
        """AppSec should store in all APM spans some tags when enabled."""

        spans = [span for _, span in interfaces.library.get_root_spans()]
        assert spans, "No root spans to validate"
        spans = [s for s in spans if s.get("type") == "web"]
        assert spans, "No spans of type web to validate"
        for span in spans:
            assert "_dd.appsec.enabled" in span["metrics"], "Cannot find _dd.appsec.enabled in span metrics"
            assert span["metrics"]["_dd.appsec.enabled"] == 1, "_dd.appsec.enabled should be 1 or 1.0"
            assert "_dd.runtime_family" in span["meta"], "Cannot find _dd.runtime_family in span meta"
            assert (
                span["meta"]["_dd.runtime_family"] in RUNTIME_FAMILIES
            ), f"_dd.runtime_family should be in {RUNTIME_FAMILIES}"

    def setup_header_collection(self):
        self.r = weblog.get("/headers", headers={"User-Agent": "Arachni/v1", "Content-Type": "text/plain"})

    @bug(context.library < f"python@{PYTHON_RELEASE_GA_1_1}", reason="a PR was not included in the release")
    @bug(context.library < "java@1.2.0", weblog_variant="spring-boot-openliberty", reason="APPSEC-6734")
    @irrelevant(context.library not in ["golang", "nodejs", "java", "dotnet"], reason="test")
    def test_header_collection(self):
        """
        AppSec should collect some headers for http.request and http.response and store them in span tags.
        Note that this test checks for collection, not data.
        """
        spans = [span for _, _, span in interfaces.library.get_spans(request=self.r)]
        assert spans, "No spans to validate"
        for span in spans:
            required_request_headers = ["user-agent", "host", "content-type"]
            required_request_headers = [f"http.request.headers.{header}" for header in required_request_headers]
            missing_request_headers = set(required_request_headers) - set(span.get("meta", {}).keys())
            assert not missing_request_headers, f"Missing request headers: {missing_request_headers}"

            required_response_headers = ["content-type", "content-length", "content-language"]
            required_response_headers = [f"http.response.headers.{header}" for header in required_response_headers]
            missing_response_headers = set(required_response_headers) - set(span.get("meta", {}).keys())
            assert not missing_response_headers, f"Missing response headers: {missing_response_headers}"

    @bug(context.library < "java@0.93.0", reason="APMRP-360")
    def test_root_span_coherence(self):
        """Appsec tags are not on span where type is not web, http or rpc"""
        valid_appsec_span_types = ["web", "http", "rpc"]
        spans = [span for _, _, span in interfaces.library.get_spans()]
        assert spans, "No spans to validate"
        assert any("_dd.appsec.enabled" in s.get("metrics", {}) for s in spans), "No appsec-enabled spans found"
        for span in spans:
            if span.get("type") in valid_appsec_span_types:
                continue
            assert "_dd.appsec.enabled" not in span.get(
                "metrics", {}
            ), f"_dd.appsec.enabled should be present only when span type is any of {', '.join(valid_appsec_span_types)}"
            assert "_dd.runtime_family" not in span.get(
                "meta", {}
            ), f"_dd.runtime_family should be present only when span type is any of {', '.join(valid_appsec_span_types)}"


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2365948382/Sensitive+Data+Obfuscation")
@features.sensitive_data_obfuscation
@features.security_events_metadata
class Test_AppSecObfuscator:
    """AppSec obfuscates sensitive data."""

    SECRET_VALUE_WITH_SENSITIVE_KEY = "this-is-a-very-secret-value-having-the-attack"
    SECRET_VALUE_WITH_NON_SENSITIVE_KEY = "not-a-sensitive-cookie-value-having-an-select-pg_sleep-attack"
    VALUE_WITH_SECRET = "BEARER lwqjedqwdoqwidmoqwndun32i"

    SECRET_VALUE_WITH_SENSITIVE_KEY_CUSTOM = "this-is-a-very-sensitive-cookie-value-having-the-aaaa-attack"
    SECRET_VALUE_WITH_NON_SENSITIVE_KEY_CUSTOM = "not-a-sensitive-cookie-value-having-an-bbbb-attack"

    def setup_appsec_obfuscator_key(self):
        self.r_key = weblog.get(
            "/waf/",
            headers={"Http-Api-Token": f"{self.SECRET_VALUE_WITH_SENSITIVE_KEY} acunetix-product"},
            params={"pwd": f"{self.SECRET_VALUE_WITH_SENSITIVE_KEY} select pg_sleep"},
        )

    def test_appsec_obfuscator_key(self):
        """General obfuscation test of several attacks on several rule addresses."""
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.

        def validate_appsec_span_tags(span, appsec_data):
            assert not nested_lookup(
                self.SECRET_VALUE_WITH_SENSITIVE_KEY, appsec_data, look_in_keys=True
            ), "The security events contain the secret value that should be obfuscated"

        interfaces.library.assert_waf_attack(self.r_key, address="server.request.headers.no_cookies")
        interfaces.library.assert_waf_attack(self.r_key, address="server.request.query")
        interfaces.library.validate_appsec(self.r_key, validate_appsec_span_tags, success_by_default=True)

    def setup_appsec_obfuscator_value(self):
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

        self.r_value = weblog.get(
            "/waf/",
            headers={"my-header": f"password={self.VALUE_WITH_SECRET} acunetix-product"},
            params={"payload": sensitive_raw_payload},
        )

    @missing_feature(library="java")
    def test_appsec_obfuscator_value(self):
        """Obfuscation test of a matching rule parameter value containing a sensitive keyword."""
        # Validate that the AppSec event do not contain VALUE_WITH_SECRET value.
        # The following payload will be sent as a raw encoded string via the request params
        # and matches an XSS attack. It contains an access token secret we shouldn't have in the event.

        def validate_appsec_span_tags(span, appsec_data):
            assert not nested_lookup(
                self.VALUE_WITH_SECRET, appsec_data, look_in_keys=True
            ), "The security events contain the secret value that should be obfuscated"

        interfaces.library.assert_waf_attack(self.r_value, address="server.request.headers.no_cookies")
        interfaces.library.assert_waf_attack(self.r_value, address="server.request.query")
        interfaces.library.validate_appsec(self.r_value, validate_appsec_span_tags, success_by_default=True)

    def setup_appsec_obfuscator_key_with_custom_rules(self):
        self.r_custom = weblog.get(
            "/waf/",
            cookies={"Bearer": f"{self.SECRET_VALUE_WITH_SENSITIVE_KEY}aaaa"},
            params={"pwd": f'{self.SECRET_VALUE_WITH_SENSITIVE_KEY} o:3:"d":3:{{}}'},
        )

    @scenarios.appsec_custom_rules
    def test_appsec_obfuscator_key_with_custom_rules(self):
        """General obfuscation test of several attacks on several rule addresses."""
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.

        def validate_appsec_span_tags(span, appsec_data):  # pylint: disable=unused-argument
            assert not nested_lookup(
                self.SECRET_VALUE_WITH_SENSITIVE_KEY, appsec_data, look_in_keys=True
            ), "The security events contain the secret value that should be obfuscated"

        interfaces.library.assert_waf_attack(self.r_custom, address="server.request.cookies")
        interfaces.library.assert_waf_attack(self.r_custom, address="server.request.query")
        interfaces.library.validate_appsec(self.r_custom, validate_appsec_span_tags, success_by_default=True)

    def setup_appsec_obfuscator_cookies_with_custom_rules(self):
        cookies = {
            "Bearer": self.SECRET_VALUE_WITH_SENSITIVE_KEY_CUSTOM,
            "Good": self.SECRET_VALUE_WITH_NON_SENSITIVE_KEY_CUSTOM,
        }
        self.r_cookies_custom = weblog.get("/waf/", cookies=cookies)

    @scenarios.appsec_custom_rules
    def test_appsec_obfuscator_cookies_with_custom_rules(self):
        """
        Specific obfuscation test for the cookies which often contain sensitive data and are
        expected to be properly obfuscated on sensitive cookies only.
        """
        # Validate that the AppSec events do not contain the following secret value.
        # Note that this value must contain an attack pattern in order to be part of the security event data
        # that is expected to be obfuscated.

        def validate_appsec_span_tags(span, appsec_data):  # pylint: disable=unused-argument
            assert not nested_lookup(
                self.SECRET_VALUE_WITH_SENSITIVE_KEY_CUSTOM, appsec_data, look_in_keys=True
            ), "Sensitive cookie is not obfuscated"
            assert nested_lookup(
                self.SECRET_VALUE_WITH_NON_SENSITIVE_KEY_CUSTOM, appsec_data, exact_match=True
            ), "Non-sensitive cookie is not reported"

        interfaces.library.assert_waf_attack(self.r_cookies_custom, address="server.request.cookies")
        interfaces.library.validate_appsec(self.r_cookies_custom, validate_appsec_span_tags, success_by_default=True)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2186870984/HTTP+header+collection")
@features.security_events_metadata
class Test_CollectRespondHeaders:
    """AppSec should collect some headers for http.response and store them in span tags."""

    def setup_header_collection(self):
        self.r = weblog.get("/headers", headers={"User-Agent": "Arachni/v1", "Content-Type": "text/plain"})

    def test_header_collection(self):
        def assertHeaderInSpanMeta(span, header):
            if header not in span["meta"]:
                raise Exception(f"Can't find {header} in span's meta")

        def validate_response_headers(span):
            for header in ["content-type", "content-length", "content-language"]:
                assertHeaderInSpanMeta(span, f"http.response.headers.{header}")
            return True

        interfaces.library.validate_spans(self.r, validate_response_headers)


@rfc("https://datadoghq.atlassian.net/wiki/spaces/APS/pages/2186870984/HTTP+header+collection")
@features.security_events_metadata
class Test_CollectDefaultRequestHeader:

    HEADERS = ["User-Agent", "Accept", "Content-Type"]

    def setup_collect_default_request_headers(self):
        self.r = weblog.get("/headers", headers={header: "myHeaderValue" for header in self.HEADERS},)

    def test_collect_default_request_headers(self):
        """
        Collect User agent and other headers and other security info when appsec is enabled.
        """

        def assertHeaderInSpanMeta(span, header):
            if header not in span["meta"]:
                raise Exception(f"Can't find {header} in span's meta")

        def validate_request_headers(span):
            for header in self.HEADERS:
                assertHeaderInSpanMeta(span, f"http.request.headers.{header.lower()}")
            return True

        interfaces.library.validate_spans(self.r, validate_request_headers)


@rfc("https://docs.google.com/document/d/1xf-s6PtSr6heZxmO_QLUtcFzY_X_rT94lRXNq6-Ghws/edit?pli=1")
@features.security_events_metadata
class Test_ExternalWafRequestsIdentification:
    def setup_external_wafs_header_collection(self):
        self.r = weblog.get(
            "/headers",
            headers={
                "X-Amzn-Trace-Id": "Root=1-65ae48bc-04fb551979979b6c57973027",
                "CloudFront-Viewer-Ja3-Fingerprint": "e7d705a3286e19ea42f587b344ee6865",
                "Cf-Ray": "230b030023ae2822-SJC",
                "X-Cloud-Trace-Context": "105445aa7843bc8bf206b12000100000/1",
                "X-Appgw-Trace-id": "ac882cd65a2712a0fe1289ec2bb6aee7",
                "X-SigSci-RequestID": "55c24b96ca84c02201000001",
                "X-SigSci-Tags": "SQLI, XSS",
                "Akamai-User-Risk": "uuid=913c4545-757b-4d8d-859d-e1361a828361;status=0",
            },
        )

    def test_external_wafs_header_collection(self):
        """
        Collect external wafs request identifier and other security info when appsec is enabled.
        """

        def assertHeaderInSpanMeta(span, header):
            if header not in span["meta"]:
                raise Exception(f"Can't find {header} in span's meta")

        def validate_request_headers(span):
            for header in [
                "x-amzn-trace-id",
                "cloudfront-viewer-ja3-fingerprint",
                "cf-ray",
                "x-cloud-trace-context",
                "x-appgw-trace-id",
                "x-sigsci-requestid",
                "x-sigsci-tags",
                "akamai-user-risk",
            ]:
                assertHeaderInSpanMeta(span, f"http.request.headers.{header}")
            return True

        interfaces.library.validate_spans(self.r, validate_request_headers)
