# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, weblog, interfaces, scenarios, rfc, missing_feature


def validate_stack_traces(request):
    spans = [s for _, s in interfaces.library.get_root_spans(request=request)]
    assert spans, "No spans to validate"

    for span in spans:
        assert "_dd.appsec.json" in span["meta"], "'_dd.appsec.json' not found in 'meta'"

        json = span["meta"]["_dd.appsec.json"]
        assert "triggers" in json, "'triggers' not found in '_dd.appsec.json'"

        triggers = json["triggers"]

        # Find all stack IDs
        stack_ids = []
        for event in triggers:
            if "stack_id" in event:
                stack_ids.append(event["stack_id"])

        # The absence of stack IDs can be considered a bug
        assert len(stack_ids) > 0, "no 'stack_id's present in 'triggers'"

        assert "meta_struct" in span, "'meta_struct' not found in span"
        assert "_dd.stack" in span["meta_struct"], "'_dd.stack' not found in 'meta_struct'"
        assert "exploit" in span["meta_struct"]["_dd.stack"], "'exploit' not found in '_dd.stack'"

        stack_traces = span["meta_struct"]["_dd.stack"]["exploit"]
        assert stack_traces, "No stack traces to validate"

        for stack in stack_traces:
            assert "language" in stack, "'language' not found in stack trace"
            assert stack["language"] in (
                "php",
                "python",
                "nodejs",
                "java",
                "dotnet",
                "go",
                "ruby",
            ), "unexpected language"

            # Ensure the stack ID corresponds to an appsec event
            assert "id" in stack, "'id' not found in stack trace"
            assert stack["id"] in stack_ids, "'id' doesn't correspond to an appsec event"

            assert "frames" in stack, "'frames' not found in stack trace"
            assert len(stack["frames"]) <= 32, "stack trace above size limit (32 frames)"


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.enmf90juqidf")
@features.rasp_stack_trace
@scenarios.appsec_rasp
class Test_StackTrace:
    """Validate stack trace generation on exploit attempts"""

    def setup_lfi_stack_trace(self):
        self.r = weblog.get("/rasp/lfi", params={"file": "../etc/passwd"})

    def test_lfi_stack_trace(self):
        assert self.r.status_code == 403
        validate_stack_traces(self.r)

    def setup_ssrf_stack_trace(self):
        self.r = weblog.get("/rasp/ssrf", params={"domain": "169.254.169.254"})

    def test_ssrf_stack_trace(self):
        assert self.r.status_code == 403
        validate_stack_traces(self.r)

    def setup_sqli_stack_trace(self):
        self.r = weblog.get("/rasp/sqli", params={"user_id": "' OR 1 = 1 --"})

    @missing_feature(library="dotnet")
    def test_sqli_stack_trace(self):
        assert self.r.status_code == 403
        validate_stack_traces(self.r)
