import json
from pathlib import Path
from typing import Any

from utils import features, pytest, scenarios
from utils.dd_types import DataDogLibraryTrace
from utils.interfaces._library.core import LibraryInterfaceValidator
from utils.interfaces._mocked_backend import _MockedBackendInterfaceValidator


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


class _FakeRequest:
    def __init__(self, rid: str) -> None:
        self._rid = rid

    def get_rid(self) -> str:
        return self._rid


@features.not_reported
@scenarios.test_the_test
def test_library_rid_index_invalidates_on_ingest(tmp_path: Path) -> None:
    rid_one = "A" * 36
    rid_two = "B" * 36
    validator = LibraryInterfaceValidator("library")
    validator.configure(str(tmp_path), replay=False)

    log_dir = Path(validator.log_folder)
    first_file = log_dir / "00001__v0.4_traces.json"
    first_file.write_text(
        json.dumps(
            {
                "log_filename": str(first_file),
                "path": "/v0.4/traces",
                "request": {
                    "content": [
                        [{"trace_id": 1, "span_id": 10, "meta": {"http.useragent": f"system_tests rid/{rid_one}"}}]
                    ]
                },
                "response": {"content": {}},
            }
        ),
        encoding="utf-8",
    )
    validator.ingest_file(str(first_file))

    # Populate cache before second file arrives
    assert len(list(validator.get_spans(request=_FakeRequest(rid_one)))) == 1  # type: ignore[arg-type]
    assert len(list(validator.get_spans(request=_FakeRequest(rid_two)))) == 0  # type: ignore[arg-type]

    second_file = log_dir / "00002__v0.4_traces.json"
    second_file.write_text(
        json.dumps(
            {
                "log_filename": str(second_file),
                "path": "/v0.4/traces",
                "request": {
                    "content": [
                        [{"trace_id": 2, "span_id": 20, "meta": {"http.useragent": f"system_tests rid/{rid_two}"}}]
                    ]
                },
                "response": {"content": {}},
            }
        ),
        encoding="utf-8",
    )
    validator.ingest_file(str(second_file))

    assert len(list(validator.get_spans(request=_FakeRequest(rid_two)))) == 1  # type: ignore[arg-type]


@features.not_reported
@scenarios.test_the_test
def test_mocked_backend_rid_index_invalidation_and_api_key_isolation(tmp_path: Path) -> None:
    rid_one = "C" * 36
    rid_two = "D" * 36
    validator = _MockedBackendInterfaceValidator()
    validator.configure(str(tmp_path), replay=False)

    log_dir = Path(validator.log_folder)
    good_file = log_dir / "00001__api_v0.2_traces.json"
    good_file.write_text(
        json.dumps(
            {
                "log_filename": str(good_file),
                "path": "/api/v0.2/traces",
                "request": {
                    "headers": [["DD-API-KEY", "key-a"]],
                    "content": {
                        "tracerPayloads": [
                            {
                                "chunks": [
                                    {
                                        "spans": [
                                            {
                                                "traceID": 1,
                                                "spanID": 10,
                                                "meta": {"http.useragent": f"system_tests rid/{rid_one}"},
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                },
                "response": {"content": {}},
            }
        ),
        encoding="utf-8",
    )
    validator.ingest_file(str(good_file))

    assert len(list(validator.get_spans(request=_FakeRequest(rid_one)))) == 1  # type: ignore[arg-type]
    assert len(list(validator.get_spans(request=_FakeRequest(rid_two)))) == 0  # type: ignore[arg-type]

    # Ingest a second valid trace + an unparseable payload from a different API key
    second_file = log_dir / "00002__api_v0.2_traces.json"
    second_file.write_text(
        json.dumps(
            {
                "log_filename": str(second_file),
                "path": "/api/v0.2/traces",
                "request": {
                    "headers": [["DD-API-KEY", "key-a"]],
                    "content": {
                        "tracerPayloads": [
                            {
                                "chunks": [
                                    {
                                        "spans": [
                                            {
                                                "traceID": 2,
                                                "spanID": 20,
                                                "meta": {"http.useragent": f"system_tests rid/{rid_two}"},
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                },
                "response": {"content": {}},
            }
        ),
        encoding="utf-8",
    )
    validator.ingest_file(str(second_file))
    assert len(list(validator.get_spans(request=_FakeRequest(rid_two)))) == 1  # type: ignore[arg-type]

    broken_other_sender = log_dir / "00003__api_v0.2_traces.json"
    broken_other_sender.write_text(
        json.dumps(
            {
                "log_filename": str(broken_other_sender),
                "path": "/api/v0.2/traces",
                "request": {"headers": [["DD-API-KEY", "key-b"]], "raw_content": "corrupt"},
                "response": {"content": {}},
            }
        ),
        encoding="utf-8",
    )
    validator.ingest_file(str(broken_other_sender))

    # Filtering by key-a must ignore key-b's broken payload
    assert len(list(validator.get_spans(request=_FakeRequest(rid_one), with_api_key="key-a"))) == 1  # type: ignore[arg-type]
