# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc, context


API10_TAGS = [
   "_dd.appsec.trace.request_headers",
   "_dd.appsec.trace.request_body",
   "_dd.appsec.trace.request_method",   
]

class API10:
    TAG:str = "undefined"
    EXPECTED_VALUE:str = "undefined"

    def validate(self, span):
        if span.get("parent_id") not in (0, None):
            return None

        assert "_dd.appsec.trace.mark" in span["meta"], "Missing _dd.appsec.trace.mark from span's meta"

        assert span["meta"][self.TAG] == self.EXPECTED_VALUE
        # ensure this is the only rule triggered
        for tag in API10_TAGS:
            assert tag == self.TAG or tag not in span["meta"]

        return True


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
class Test_API10_request_headers(API10):
    """Shell Injection through query parameters"""
    TAG = "_dd.appsec.trace.request_headers"
    EXPECTED_VALUE = "TAG_API10_REQ_HEADERS"

    def setup_api10_get_headers(self):
        self.r = weblog.get("/external_request", params={"Witness": "pwq3ojtropiw3hjtowir"})

    def test_api10_get_headers(self):
        assert self.r.status_code == 200
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate)


@rfc("https://docs.google.com/document/d/1gCXU3LvTH9en3Bww0AC2coSJWz1m7HcavZjvMLuDCWg/edit#heading=h.giijrtyn1fdx")
@features.api10
@scenarios.appsec_rasp
class Test_API10_request_method:
    """Shell Injection through query parameters"""
    TAG = "_dd.appsec.trace.request_method"
    EXPECTED_VALUE = "TAG_API10_REQ_METHOD"

    def setup_api10_get_headers(self):
        self.r = weblog.request("TRACE","/external_request")

    def test_api10_get_headers(self):
        assert self.r.status_code == 200
        print()
        print(self.r.headers)
        print(self.r.text)
        body = json.loads(self.r.text)
        assert "error" not in body
        assert int(body["status"]) == 200
        interfaces.library.validate_spans(self.r, validator=self.validate)
