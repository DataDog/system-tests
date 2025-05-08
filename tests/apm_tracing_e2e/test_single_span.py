from utils import context, weblog, interfaces, rfc, scenarios, missing_feature, features
from utils.dd_constants import (
    SAMPLING_PRIORITY_KEY,
    SINGLE_SPAN_SAMPLING_MECHANISM,
    SINGLE_SPAN_SAMPLING_MECHANISM_VALUE,
    SINGLE_SPAN_SAMPLING_RATE,
    SINGLE_SPAN_SAMPLING_MAX_PER_SEC,
)


@rfc("ATI-2419")
@missing_feature(context.agent_version < "7.40", reason="Single Spans is not available in agents pre 7.40.")
@scenarios.apm_tracing_e2e_single_span
@features.single_span_ingestion_control
class Test_SingleSpan:
    """This is a test that exercises the Single Span Ingestion Control feature.
    Read more about Single Span at https://docs.datadoghq.com/tracing/trace_pipeline/ingestion_mechanisms/?tab=java#single-spans

    The tests below depend on the `.single_span_submitted` suffix to be part of the `DD_SPAN_SAMPLING_RULES`
    configuration defined for this scenario in `run.sh`
    """

    def setup_parent_span_is_single_span(self):
        self.req = weblog.get(
            "/e2e_single_span",
            {"shouldIndex": 1, "parentName": "parent.span.single_span_submitted", "childName": "child.span"},
        )

    def test_parent_span_is_single_span(self):
        # Only the parent span should be submitted to the backend!
        spans = interfaces.agent.get_spans_list(self.req)
        assert len(spans) == 1, "Agent did not submit the spans we want!"

        # Assert the spans sent by the agent.
        span = spans[0]
        assert span["name"] == "parent.span.single_span_submitted"
        assert span.get("parentID") is None
        assert span["metrics"]["_dd.top_level"] == 1.0
        _assert_single_span_metrics(span)

        # Assert the spans received from the backend!
        spans = interfaces.backend.assert_single_spans_exist(self.req)
        assert len(spans) == 1
        _assert_single_span_event(spans[0], "parent.span.single_span_submitted", is_root=True)

    def setup_child_span_is_single_span(self):
        self.req = weblog.get(
            "/e2e_single_span",
            {"shouldIndex": 1, "parentName": "parent.span", "childName": "child.span.single_span_submitted"},
        )

    def test_child_span_is_single_span(self):
        # Only the child should be submitted to the backend!
        spans = interfaces.agent.get_spans_list(self.req)
        assert len(spans) == 1, "Agent did not submit the spans we want!"

        # Assert the spans sent by the agent.
        span = spans[0]
        assert span["name"] == "child.span.single_span_submitted"
        assert span["parentID"] is not None
        _assert_single_span_metrics(span)

        # Assert the spans received from the backend!
        spans = interfaces.backend.assert_single_spans_exist(self.req)
        assert len(spans) == 1
        _assert_single_span_event(spans[0], "child.span.single_span_submitted", is_root=False)


def _assert_single_span_event(event, name, is_root):
    assert event["operation_name"] == name
    assert event["single_span"] is True
    assert event["ingestion_reason"] == "single_span"
    parent_id = event["parent_id"]
    if is_root:
        assert parent_id == "0"
    else:
        assert parent_id != "0", f"In a child span the parent_id should be specified. Actual: {parent_id}"
        assert len(parent_id) > 0, f"In a child span the parent_id should be specified. Actual: {parent_id}"


def _assert_single_span_metrics(span):
    assert span["metrics"][SAMPLING_PRIORITY_KEY] == -1  # due to the global sampling rate = 0
    assert span["metrics"][SINGLE_SPAN_SAMPLING_RATE] == 1.0
    assert span["metrics"][SINGLE_SPAN_SAMPLING_MECHANISM] == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
    assert span["metrics"][SINGLE_SPAN_SAMPLING_MAX_PER_SEC] == 50.0
