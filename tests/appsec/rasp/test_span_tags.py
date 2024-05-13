# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc, missing_feature


def validate_span_tags(span, expected_meta=[], expected_metrics=[]):
    """Validate RASP span tags are added when an event is generated"""

    meta = span["meta"]
    for m in expected_meta:
        assert m in meta, f"missing span meta tag `{m}` in {meta}"

    metrics = span["metrics"]
    for m in expected_metrics:
        assert m in metrics, f"missing span metric tag `{m}` in {metrics}"


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@scenarios.appsec_rasp
class Test_Mandatory_SpanTags:
    """ Validate span tag generation on exploit attempts """

    def setup_lfi_span_tags(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_span_tags(self):
        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_span_tags(span, expected_metrics=["appsec.rasp.duration"])

    def setup_ssrf_span_tags(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_span_tags(self):
        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_span_tags(span, expected_metrics=["appsec.rasp.duration"])

    def setup_sqli_span_tags(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    @missing_feature(library="python")
    @missing_feature(library="dotnet")
    def test_sqli_span_tags(self):
        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_span_tags(span, expected_metrics=["appsec.rasp.duration"])


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.96mezjnqf46y")
@features.rasp_span_tags
@scenarios.appsec_rasp
class Test_Optional_SpanTags:
    """ Validate span tag generation on exploit attempts """

    def setup_lfi_span_tags(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_span_tags(self):
        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_span_tags(span, expected_metrics=["appsec.rasp.duration_ext", "appsec.rasp.rule.eval"])

    def setup_ssrf_span_tags(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_span_tags(self):
        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_span_tags(span, expected_metrics=["appsec.rasp.duration_ext", "appsec.rasp.rule.eval"])

    def setup_sqli_span_tags(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    def test_sqli_span_tags(self):
        for _, span in interfaces.library.get_root_spans(request=self.r):
            validate_span_tags(span, expected_metrics=["appsec.rasp.duration_ext", "appsec.rasp.rule.eval"])
