"""Self-tests ensure the opt-out oracle rejects leaks and missing positive controls."""

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from tests.ffe.utils.evaluation_telemetry import (
    assert_count,
    assert_evaluation_responses,
    assert_metric_activity,
    assert_setup_succeeded,
    evaluation_count,
    evaluation_setup_error,
)
from utils import HttpResponse, features, pytest, scenarios


@scenarios.test_the_test
@features.not_reported
@pytest.mark.parametrize(
    ("status_code", "text", "count", "passes"),
    [
        (200, '{"value": "on-value"}', 3, True),
        (500, '{"value": "on-value"}', 3, False),
        (200, '{"value": "default"}', 3, False),
        (200, "not JSON", 3, False),
        (200, "{}", 3, False),
        (200, '{"value": "on-value"}', 0, False),
    ],
)
def test_evaluation_response_oracle(status_code: int, text: str, count: int, *, passes: bool) -> None:
    response = HttpResponse(
        {
            "request": {"method": "POST", "url": "http://weblog/ffe", "params": None},
            "status_code": status_code,
            "text": text,
            "cookies": {},
        }
    )
    responses = [response] * count
    if passes:
        assert_evaluation_responses(responses, expected_count=3, expected_value="on-value")
    else:
        with pytest.raises((AssertionError, ValueError, KeyError)):
            assert_evaluation_responses(responses, expected_count=3, expected_value="on-value")


@scenarios.test_the_test
@features.not_reported
@pytest.mark.parametrize(
    ("suppressed_count", "allowed_count", "passes"),
    [(0, 3, True), (3, 3, False), (0, 0, False), (0, 6, False)],
)
def test_opt_out_evp_oracle(suppressed_count: int, allowed_count: int, *, passes: bool) -> None:
    events = [
        {"flag": {"key": flag}, "evaluation_count": count}
        for flag, count in [("suppressed", suppressed_count), ("allowed", allowed_count)]
        if count
    ]
    captures: list[dict[str, Any]] = [
        {"path": "/api/v2/flagevaluation", "request": {"content": {"flagEvaluations": events}}}
    ]

    def validate() -> None:
        assert_count(evaluation_count(captures, "suppressed"), 0, "suppressed")
        assert_count(evaluation_count(captures, "allowed"), 3, "allowed")

    if passes:
        validate()
    else:
        with pytest.raises(AssertionError, match="expected.*evaluations"):
            validate()


@scenarios.test_the_test
@features.not_reported
@pytest.mark.parametrize(
    ("values", "suppressed", "passes"),
    [
        ([3, 3, 3], False, True),  # Repeated cumulative snapshots are not three separate counts.
        ([1, 2, 3, 3], False, True),
        ([1, 1, 1], False, True),  # Delta exports are also valid.
        ([], False, False),
        ([0, 0], False, False),
        ([], True, True),
        ([0, 0], True, True),
        ([1, 0], True, False),  # A later zero does not hide earlier leaked telemetry.
        ([3, 3, 3], True, False),
        ([-1, 1], True, False),  # Points must not cancel each other out.
    ],
)
@pytest.mark.parametrize("point_format", ["dict", "list"])
def test_opt_out_metric_oracle(values: list[int], point_format: str, *, suppressed: bool, passes: bool) -> None:
    points = [
        {"timestamp": index, "value": value} if point_format == "dict" else [index, value]
        for index, value in enumerate(values)
    ]
    metrics: list[dict[str, Any]] = [
        {"metric": "feature_flag.evaluations", "tags": ["feature_flag.key:subject-flag"], "points": points},
        {"metric": "feature_flag.evaluations", "tags": ["feature_flag.key:other-flag"], "points": [[1, 99]]},
        {"metric": "unrelated.metric", "tags": ["feature_flag.key:subject-flag"], "points": [[1, 99]]},
    ]
    if passes:
        assert_metric_activity(metrics, "subject-flag", suppressed=suppressed)
    else:
        with pytest.raises(AssertionError, match="subject-flag"):
            assert_metric_activity(metrics, "subject-flag", suppressed=suppressed)


@scenarios.test_the_test
@features.not_reported
@pytest.mark.parametrize("failure_source", ["remote-config", "worker-request"])
def test_evaluation_setup_failure_is_deferred(failure_source: str) -> None:
    error = TimeoutError(f"{failure_source} timed out")
    completed: list[str] = []

    def fail() -> None:
        raise error

    def prepare() -> None:
        if failure_source == "worker-request":
            with ThreadPoolExecutor(max_workers=1) as executor:
                list(executor.map(lambda _: fail(), [None]))
        else:
            fail()

    # Setup errors must not stop the next setup or its validation.
    setup_error = evaluation_setup_error(prepare)
    later_error = evaluation_setup_error(lambda: completed.append("later setup"))
    assert completed == ["later setup"]
    assert_setup_succeeded(later_error)
    # Setup properties must survive the harness's JSON replay storage.
    restored_error = json.loads(json.dumps(setup_error))
    assert f"TimeoutError: {failure_source} timed out" in restored_error
    with pytest.raises(AssertionError, match=failure_source):
        assert_setup_succeeded(restored_error)


@scenarios.test_the_test
@features.not_reported
def test_evaluation_setup_does_not_swallow_interrupts() -> None:
    def interrupt() -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        evaluation_setup_error(interrupt)
