"""Shared IAST assertions at Agent-to-backend intake, independent of SDK trace transport."""

import json
from pathlib import Path
from typing import Any

import jsonschema

from utils import interfaces, weblog
from utils.dd_constants import SamplingPriority
from utils.dd_types import DataDogAgentSpan


# The harness mounts this directory in every weblog. No traversal or application file is needed.
_SMOKE_PATH = "/var/log/system-tests"
_SCHEMA = json.loads((Path(__file__).parents[1] / "iast/vulnerability_schema.json").read_text(encoding="utf-8"))


def _assert_report(report: dict[str, Any]) -> set[str]:
    """Check the source/evidence link in this carrier and return the referenced stack IDs."""
    jsonschema.validate(report, _SCHEMA)
    source_indices = {
        i
        for i, source in enumerate(report.get("sources", []))
        if source.get("name") == "path" and source.get("value") == _SMOKE_PATH
    }
    assert source_indices, "IAST report lost the submitted path source"

    findings = [finding for finding in report["vulnerabilities"] if finding["type"] == "PATH_TRAVERSAL"]
    assert findings, "IAST report lost the path finding"
    stack_ids = set()
    for finding in findings:
        parts = finding["evidence"].get("valueParts", [])
        assert any(part.get("source") in source_indices and _SMOKE_PATH in part.get("value", "") for part in parts), (
            "IAST evidence does not point to the submitted path"
        )
        stack_id = finding["location"].get("stackId")
        assert isinstance(stack_id, str), "IAST finding lost its stackId"
        assert stack_id, "IAST finding has an empty stackId"
        stack_ids.add(stack_id)
    return stack_ids


def _assert_stacks(span: DataDogAgentSpan, expected: set[str]) -> None:
    stacks = span.get_structured_payloads("_dd.stack")
    assert stacks, "Backend did not receive the IAST stack carrier"
    for payload in stacks:
        seen = set()
        for stack in payload.get("vulnerability", []):
            if stack.get("id") in expected:
                assert isinstance(stack.get("language"), str)
                assert stack["language"], "IAST stack lost its language"
                frames = stack.get("frames")
                assert isinstance(frames, list)
                assert frames, "IAST stack lost its frames"
                seen.add(stack["id"])
        assert expected <= seen, f"IAST stacks missing for findings: {expected - seen}"


def _has_executed_sink_metric() -> bool:
    # The intake records telemetry per SDK, not per trace. Match the specific sink, not another IAST check.
    for data in interfaces.mocked_backend.get_telemetry_data(flatten_message_batches=False):
        content = data["request"]["content"]
        if content.get("request_type") != "generate-metrics":
            continue
        payload = content["payload"]
        for series in payload.get("series", []):
            if (
                (series.get("namespace") or payload.get("namespace")) == "iast"
                and series.get("metric") == "executed.sink"
                and "vulnerability_type:path_traversal" in map(str.lower, series.get("tags", []))
                and any(value > 0 for _, value in series.get("points", []))
            ):
                return True
    return False


class BaseIastSmokeTests:
    """Verify IAST report, stack, retention and telemetry carriers from a native smoke request."""

    def setup_iast_smoke(self) -> None:
        self.r = weblog.post("/iast/path_traversal/test_insecure", data={"path": _SMOKE_PATH})

    def test_iast_smoke(self) -> None:
        assert self.r.status_code == 200
        report_spans = [
            (span, reports)
            for _, span in interfaces.mocked_backend.get_spans(self.r)
            if (reports := span.get_structured_payloads("iast", "_dd.iast.json"))
        ]
        assert report_spans, "Backend did not receive an IAST report for this request"
        for span, reports in report_spans:
            assert span.get_sampling_priority() == SamplingPriority.USER_KEEP
            enabled = span.metrics.get("_dd.iast.enabled", span.meta.get("_dd.iast.enabled"))
            assert not isinstance(enabled, bool)
            assert enabled in (1, "1"), f"Unexpected _dd.iast.enabled: {enabled!r}"
            for report in reports:
                _assert_stacks(span, _assert_report(report))
        assert _has_executed_sink_metric(), (
            "Backend did not receive positive IAST executed.sink telemetry for this sink"
        )
