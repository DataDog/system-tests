# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json

from utils import weblog, interfaces, scenarios, features
from utils._weblog import HttpResponse
from utils.dd_constants import SamplingPriority

# Arbitrary upstream trace context, the ids only have to be stable and non-zero
UPSTREAM_TRACE_ID = 1212121212121212121
UPSTREAM_PARENT_ID = 34343434


def _upstream_headers(sampling_priority: SamplingPriority) -> dict[str, str]:
    return {
        "x-datadog-trace-id": str(UPSTREAM_TRACE_ID),
        "x-datadog-parent-id": str(UPSTREAM_PARENT_ID),
        "x-datadog-sampling-priority": str(int(sampling_priority)),
    }


def _assert_upstream_trace_continued(request: HttpResponse) -> None:
    """Without this check, a weblog that does not extract the upstream context at all would start a
    fresh trace, and the manual decision alone would still yield the expected priority.
    """
    spans = [span for _, _, span in interfaces.library.get_spans(request=request)]
    assert spans, "No span reported for that request"

    trace_ids = {span["trace_id"] for span in spans}
    assert all(span.trace_id_equals(UPSTREAM_TRACE_ID) for span in spans), (
        f"Spans do not belong to the upstream trace: {trace_ids}"
    )

    parent_ids = {span.get("parent_id") for span in spans}
    assert UPSTREAM_PARENT_ID in parent_ids, f"No span is a child of the upstream span: {parent_ids}"


def _assert_decision_propagated_downstream(request: HttpResponse, expected: SamplingPriority) -> None:
    """The endpoint calls downstream once the decision has been applied, and reports the headers it
    sent. The propagated priority must be the manual decision, not the upstream one.
    """
    request_headers = json.loads(request.text)["request_headers"]

    # Case-insensitive lookup, as the header casing depends on the weblog app implementation, and some
    # weblogs report the headers as a list of objects instead of a dict
    if isinstance(request_headers, dict):
        propagated = next(
            (value for key, value in request_headers.items() if key.lower() == "x-datadog-sampling-priority"), None
        )
    else:
        propagated = next(
            (
                header.get("value")
                for header in request_headers
                if header.get("key", "").lower() == "x-datadog-sampling-priority"
            ),
            None,
        )

    assert propagated is not None, f"No sampling priority propagated downstream: {request_headers}"
    assert int(propagated) == expected, f"Propagated sampling priority is {propagated}, expected {int(expected)}"


def _get_sampling_priority(request: HttpResponse) -> int:
    """Sampling priority is reported on the local root span of the trace chunk, which is the
    weblog span here, as the trace is continued from an upstream service.
    """
    priorities = {
        span["metrics"]["_sampling_priority_v1"]
        for _, _, span in interfaces.library.get_spans(request=request)
        if "_sampling_priority_v1" in span.get("metrics", {})
    }

    assert priorities, "No span reported a _sampling_priority_v1 metric for that request"
    assert len(priorities) == 1, f"Spans of the same trace disagree on the sampling priority: {priorities}"

    return priorities.pop()


@scenarios.sampling
@features.ensure_that_sampling_is_consistent_across_languages
class Test_Manual_Sampling:
    """The manual keep/drop API overrides the sampling decision transmitted by an upstream service"""

    def setup_manual_keep_overrides_upstream_drop(self):
        self.r_keep = weblog.get(
            "/trace/manual_keep_drop",
            params={"decision": "keep"},
            headers=_upstream_headers(SamplingPriority.AUTO_REJECT),
        )

    def test_manual_keep_overrides_upstream_drop(self):
        assert self.r_keep.status_code == 200
        _assert_upstream_trace_continued(self.r_keep)
        assert _get_sampling_priority(self.r_keep) == SamplingPriority.USER_KEEP
        _assert_decision_propagated_downstream(self.r_keep, SamplingPriority.USER_KEEP)

    def setup_manual_drop_overrides_upstream_keep(self):
        self.r_drop = weblog.get(
            "/trace/manual_keep_drop",
            params={"decision": "drop"},
            headers=_upstream_headers(SamplingPriority.USER_KEEP),
        )

    def test_manual_drop_overrides_upstream_keep(self):
        assert self.r_drop.status_code == 200
        _assert_upstream_trace_continued(self.r_drop)
        assert _get_sampling_priority(self.r_drop) == SamplingPriority.USER_REJECT
        _assert_decision_propagated_downstream(self.r_drop, SamplingPriority.USER_REJECT)
