# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import interfaces


def validate_span_tags(request, expected_meta=[], expected_metrics=[]):
    """Validate RASP span tags are added when an event is generated"""
    spans = [s for _, s in interfaces.library.get_root_spans(request=request)]
    assert spans, "No spans to validate"

    for span in spans:
        meta = span["meta"]
        for m in expected_meta:
            assert m in meta, f"missing span meta tag `{m}` in {meta}"

        metrics = span["metrics"]
        for m in expected_metrics:
            assert m in metrics, f"missing span metric tag `{m}` in {metrics}"


def validate_stack_traces(request):
    events = list(interfaces.library.get_appsec_events(request=request))
    assert len(events) != 0, "No appsec event has been reported"

    for _, _, span, appsec_data in events:
        assert "triggers" in appsec_data, "'triggers' not found in appsec_data"

        triggers = appsec_data["triggers"]

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
