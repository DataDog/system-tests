from typing import Any

from utils import features, pytest, scenarios
from utils.dd_types import DataDogLibraryTrace


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize("path", ["/v0.4/traces", "/v0.5/traces"])
def test_legacy_span_without_metrics_has_no_sampling_priority(path: str) -> None:
    trace = DataDogLibraryTrace.from_legacy({"path": path}, [{"trace_id": 42}])

    assert trace[0].get_sampling_priority() is None


@features.not_reported
@scenarios.test_the_test
@pytest.mark.parametrize("priority", [-1, 0, 1, 2])
def test_v1_spans_use_chunk_sampling_priority(priority: int) -> None:
    raw_trace: dict[str, Any] = {
        "trace_id": "0x0000000000000000000000000000002a",
        "priority": priority,
        "spans": [{"attributes": {"bool": True}}, {"attributes": {"int": 123}}],
    }
    trace = DataDogLibraryTrace.from_v1({"path": "/v1.0/traces"}, raw_trace)

    for span in trace:
        assert span.get_sampling_priority() == priority
        assert "_sampling_priority_v1" not in span.metrics
    assert trace[0].meta["bool"] is True
    assert trace[1].meta["int"] == 123
