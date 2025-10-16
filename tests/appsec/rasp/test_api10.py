# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import urllib.parse

from utils import features, weblog, interfaces, scenarios, rfc

from tests.appsec.rasp.utils import (
    find_series,
    validate_metric_variant_v2,
)

API10_TAGS = [
    "_dd.appsec.trace.req_headers",
    "_dd.appsec.trace.req_body",
    "_dd.appsec.trace.req_method",
    "_dd.appsec.trace.res_status",
    "_dd.appsec.trace.res_headers",
    "_dd.appsec.trace.res_body",
]


class API10:
    TAGS_EXPECTED: list[tuple[str, str]] = []

    def validate(self, span):
        if span.get("parent_id") not in (0, None):
            return None

        for tag, expected in self.TAGS_EXPECTED:
            assert tag in span["meta"], f"Missing {tag} from span's meta"

            assert span["meta"][tag] == expected, f"Wrong value {span["meta"][tag]}, expected {expected}"

        # ensure this is the only rule(s) triggered
        tags = [t[0] for t in self.TAGS_EXPECTED]
        for tag in API10_TAGS:
            assert tag in tags or tag not in span["meta"]

        return True

    def validate_metric(self, span):
        for tag, expected in self.TAGS_EXPECTED:
            # check also in meta to be safe
            assert tag in span["metrics"] or tag in span["meta"], f"Missing {tag} from span's meta/metrics"
            values = span["metrics"] if tag in span["metrics"] else span["meta"]
            
            # Try numeric comparison first, fallback to string comparison
            try:
                assert float(values[tag]) == float(expected), f"Wrong value {values[tag]}, expected {expected}"
            except (ValueError, TypeError):
                assert str(values[tag]) == expected, f"Wrong value {values[tag]}, expected {expected}"

        return True


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_request_headers(API10):
    """API 10 for request headers"""

    TAGS_EXPECTED = [("_dd.appsec.trace.req_headers", "TAG_API10_REQ_HEADERS")]
    PARAMS = {"Witness": "pwq3ojtropiw3hjtowir"}

    def setup_api10_req_headers(self):
        self.r = weblog.get("/external_request", params=self.PARAMS)

    def test_api10_req_headers(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_request_method(API10):
    """API 10 for request method"""

    TAGS_EXPECTED = [("_dd.appsec.trace.req_method", "TAG_API10_REQ_METHOD")]

    def setup_api10_req_method(self):
        self.r = weblog.request("TRACE", "/external_request")

    def test_api10_req_method(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_request_body(API10):
    """API 10 for request body"""

    TAGS_EXPECTED = [("_dd.appsec.trace.req_body", "TAG_API10_REQ_BODY")]
    BODY = {"payload_in": "qw2jedrkjerbgol23ewpfirj2qw3or"}

    def setup_api10_req_body(self):
        self.r = weblog.request(
            "POST", "/external_request", data=json.dumps(self.BODY), headers={"Content-Type": "application/json"}
        )

    def test_api10_req_body(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_response_status(API10):
    """API 10 for response status"""

    TAGS_EXPECTED = [("_dd.appsec.trace.res_status", "TAG_API10_RES_STATUS")]
    PARAMS = {"status": "201"}

    def setup_api10_res_status(self):
        self.r = weblog.get("/external_request", params=self.PARAMS)

    def test_api10_res_status(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 201
        interfaces.library.validate_spans(self.r, validator=self.validate)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_response_headers(API10):
    """API 10 for response headers."""

    TAGS_EXPECTED = [("_dd.appsec.trace.res_headers", "TAG_API10_RES_HEADERS")]
    PARAMS = {"url_extra": "?echo-headers=qwoierj12l3"}

    def setup_api10_res_headers(self):
        self.r = weblog.get("/external_request", params=self.PARAMS)

    def test_api10_res_headers(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_response_body(API10):
    """API 10 for response body."""

    TAGS_EXPECTED = [("_dd.appsec.trace.res_body", "TAG_API10_RES_BODY")]
    BODY = {"payload_out": "kqehf09123r4lnksef"}

    def setup_api10_res_body(self):
        self.r = weblog.post(
            "/external_request", data=json.dumps(self.BODY), headers={"Content-Type": "application/json"}
        )

    def test_api10_res_body(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_all(API10):
    """API 10 for all addresses at the same time."""

    TAGS_EXPECTED = [
        ("_dd.appsec.trace.req_headers", "TAG_API10_REQ_HEADERS"),
        ("_dd.appsec.trace.req_method", "TAG_API10_REQ_METHOD"),
        ("_dd.appsec.trace.req_body", "TAG_API10_REQ_BODY"),
        ("_dd.appsec.trace.res_status", "TAG_API10_RES_STATUS"),
        ("_dd.appsec.trace.res_headers", "TAG_API10_RES_HEADERS"),
        ("_dd.appsec.trace.res_body", "TAG_API10_RES_BODY"),
    ]

    BODY = {"payload_in": "qw2jedrkjerbgol23ewpfirj2qw3or", "payload_out": "kqehf09123r4lnksef"}
    PARAMS = {"Witness": "pwq3ojtropiw3hjtowir", "status": "201", "url_extra": "?echo-headers=qwoierj12l3"}

    def setup_api10(self):
        self.r = weblog.request(
            "PUT",
            "/external_request?" + urllib.parse.urlencode(self.PARAMS),
            data=json.dumps(self.BODY),
            headers={"Content-Type": "application/json"},
        )

    def test_api10(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 201
        interfaces.library.validate_spans(self.r, validator=self.validate)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_downstream_request_tag(API10):
    """API 10 span tag validation"""

    TAGS_EXPECTED = [
        ("_dd.appsec.downstream_request", "1"),
    ]

    def setup_api10_req_method(self):
        self.r = weblog.request("TRACE", "/external_request")

    def test_api10_req_method(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        interfaces.library.validate_spans(self.r, validator=self.validate_metric)

@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
@scenarios.appsec_standalone_rasp
class Test_API10_downstream_ssrf_telemetry(API10):
    """API 10 span telemetry validation"""

    PARAMS = {"url_extra": "?echo-headers=qwoierj12l3", "Witness": "pwq3ojtropiw3hjtowir"}
    def setup_api10_req(self):
        self.r = weblog.get("/external_request", params=self.PARAMS)

    def test_api10_req(self):
        series_eval = find_series("appsec", "rasp.rule.eval", is_metrics=True)
        assert series_eval
        assert any(validate_metric_variant_v2("rasp.rule.eval", "ssrf", "request", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]
        assert any(validate_metric_variant_v2("rasp.rule.eval", "ssrf", "response", s) for s in series_eval), [
            s.get("tags") for s in series_eval
        ]

        series_match = find_series("appsec", "rasp.rule.match", is_metrics=True)
        assert series_match

        assert any(validate_metric_variant_v2("rasp.rule.match", "ssrf", "request", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]
        assert any(validate_metric_variant_v2("rasp.rule.match", "ssrf", "response", s) for s in series_match), [
            s.get("tags") for s in series_match
        ]


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7Cwg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp_without_downstream_body_analysis_using_sample_rate
class Test_API10_without_downstream_body_analysis_using_sample_rate(API10):
    """API 10 without downstream body analysis"""

    TAGS_NOT_EXPECTED = ["_dd.appsec.trace.res_body"]
    BODY = {"payload_out": "kqehf09123r4lnksef"}

    def setup_api10_res_body(self):
        self.r = weblog.post(
            "/external_request", data=json.dumps(self.BODY), headers={"Content-Type": "application/json"}
        )

    def validate_absence(self, span):
        if span.get("parent_id") not in (0, None):
            return None

        for tag in self.TAGS_NOT_EXPECTED:
            assert tag not in span.get("meta", {}), f"Tag {tag} should NOT be present in span's meta"

        return True

    def test_api10_res_body(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate_absence)

@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7Cwg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp_without_downstream_body_analysis_using_max
class Test_API10_without_downstream_body_analysis_using_max(API10):
    """API 10 without downstream body analysis"""

    TAGS_NOT_EXPECTED = ["_dd.appsec.trace.res_body"]
    BODY = {"payload_out": "kqehf09123r4lnksef"}

    def setup_api10_res_body(self):
        self.r = weblog.post(
            "/external_request", data=json.dumps(self.BODY), headers={"Content-Type": "application/json"}
        )

    def validate_absence(self, span):
        if span.get("parent_id") not in (0, None):
            return None

        for tag in self.TAGS_NOT_EXPECTED:
            assert tag not in span.get("meta", {}), f"Tag {tag} should NOT be present in span's meta"

        return True

    def test_api10_res_body(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate_absence)

