# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json

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


def find_series(is_metrics: bool, namespace, metric):
    request_type = "generate-metrics" if is_metrics else "distributions"
    series = []
    for data in interfaces.library.get_telemetry_data():
        content = data["request"]["content"]
        if content.get("request_type") != request_type:
            continue
        fallback_namespace = content["payload"].get("namespace")
        for serie in content["payload"]["series"]:
            computed_namespace = serie.get("namespace", fallback_namespace)
            # Inject here the computed namespace considering the fallback. This simplifies later assertions.
            serie["_computed_namespace"] = computed_namespace
            if computed_namespace == namespace and serie["metric"] == metric:
                series.append(serie)
    return series


def validate_metric(name, type, metric):
    return (
        metric.get("metric") == name
        and metric.get("type") == "count"
        and f"rule_type:{type}" in metric.get("tags", ())
        and any(s.startswith("waf_version:") for s in metric.get("tags", ()))
    )

def validate_metric_variant(name, type, variant, metric):
    return (
        metric.get("metric") == name
        and metric.get("type") == "count"
        and f"rule_type:{type}" in metric.get("tags", ())
        and f"rule_variant:{variant}" in metric.get("tags", ())
        and any(s.startswith("waf_version:") for s in metric.get("tags", ()))
    )

def validate_metric_tag_version(tag_prefix, min_version, metric):
    for tag in metric["tags"]:
        if tag.startswith(tag_prefix + ":"):
            version_str = tag.split(":")[1]
            current_version = list(map(int, version_str.split(".")))
            if current_version >= min_version:
                return True
    return False


def _load_file(file_path):
    with open(file_path, "r") as f:
        return json.load(f)


class RC_CONSTANTS:
    CONFIG_ENABLED = (
        "datadog/2/ASM_FEATURES/asm_features_activation/config",
        {"asm": {"enabled": True}},
    )
    BLOCK_405 = (
        "datadog/2/ASM/actions/config",
        {"actions": [{"id": "block", "parameters": {"status_code": 405, "type": "json"}, "type": "block_request",}]},
    )

    BLOCK_505 = (
        "datadog/2/ASM/actions/config",
        {"actions": [{"id": "block", "parameters": {"status_code": 505, "type": "html"}, "type": "block_request",}]},
    )

    BLOCK_REDIRECT = (
        "datadog/2/ASM/actions/config",
        {
            "actions": [
                {
                    "id": "block",
                    "parameters": {"location": "http://google.com", "status_code": 302},
                    "type": "redirect_request",
                }
            ]
        },
    )

    RULES = (
        "datadog/2/ASM_DD/rules/config",
        _load_file("./tests/appsec/rasp/rasp_ruleset.json"),
    )


class Base_Rules_Version:
    """Test libddwaf version"""

    min_version = "1.13.3"

    def test_min_version(self):
        """Checks data in waf.init metric to verify waf version"""

        min_version_array = list(map(int, self.min_version.split(".")))
        series = find_series(True, "appsec", "waf.init")
        assert series
        assert any(validate_metric_tag_version("event_rules_version", min_version_array, s) for s in series)
