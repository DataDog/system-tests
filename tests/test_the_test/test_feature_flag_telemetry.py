"""Unit coverage for route-aware Feature Flags telemetry capture."""

from types import SimpleNamespace

import pytest

from tests.ffe.utils.telemetry import assert_expected_telemetry_route
from utils import context, features, scenarios
from utils.interfaces._feature_flag_telemetry import FeatureFlagTelemetryInterfaceValidator, metric_points_from_data


@scenarios.test_the_test
@features.not_reported
def test_normalizes_direct_otlp_metric_attributes() -> None:
    data = {
        "path": "/v1/metrics",
        "request": {
            "content": {
                "resourceMetrics": [
                    {
                        "scopeMetrics": [
                            {
                                "metrics": [
                                    {
                                        "name": "feature_flag.evaluations",
                                        "sum": {
                                            "dataPoints": [
                                                {
                                                    "attributes": [
                                                        {
                                                            "key": "feature_flag.key",
                                                            "value": {"stringValue": "checkout"},
                                                        },
                                                        {
                                                            "key": "feature_flag.result.variant",
                                                            "value": {"stringValue": "on"},
                                                        },
                                                    ]
                                                }
                                            ]
                                        },
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        },
    }

    assert list(metric_points_from_data(data)) == [
        {
            "metric": "feature_flag.evaluations",
            "tags": ["feature_flag.key:checkout", "feature_flag.result.variant:on"],
            "point": {
                "attributes": [
                    {"key": "feature_flag.key", "value": {"stringValue": "checkout"}},
                    {"key": "feature_flag.result.variant", "value": {"stringValue": "on"}},
                ]
            },
        }
    ]


@scenarios.test_the_test
@features.not_reported
def test_preserves_sidecar_datadog_metric_series() -> None:
    point = {
        "metric": "feature_flag.evaluations",
        "tags": ["feature_flag.key:checkout"],
    }
    data = {
        "path": "/api/intake/metrics/v3/series",
        "request": {"content": {"series": [point]}},
    }

    assert list(metric_points_from_data(data)) == [point]


@scenarios.test_the_test
@features.not_reported
def test_replay_route_assertion_checks_recorded_unexpected_route(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = FeatureFlagTelemetryInterfaceValidator("expected")
    unexpected = FeatureFlagTelemetryInterfaceValidator("unexpected")
    expected.configure("unused", replay=True)
    unexpected.configure("unused", replay=True)

    matching_data = {"path": "/api/v2/exposures"}
    expected._append_data(matching_data)  # noqa: SLF001 - focused replay fixture
    monkeypatch.setattr(
        context,
        "scenario",
        SimpleNamespace(
            name="REPLAY_ROUTE_TEST",
            telemetry_route="sidecar",
            telemetry_interface=expected,
            unexpected_telemetry_interface=unexpected,
        ),
    )
    matcher = lambda data: data.get("path") == "/api/v2/exposures"  # noqa: E731 - compact test matcher

    assert_expected_telemetry_route(matcher, "exposure event")

    unexpected._append_data(matching_data)  # noqa: SLF001 - focused replay fixture
    with pytest.raises(AssertionError, match="duplicated through the non-selected telemetry route"):
        assert_expected_telemetry_route(matcher, "exposure event")
