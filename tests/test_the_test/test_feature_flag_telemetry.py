"""Unit coverage for route-aware Feature Flags telemetry capture."""

from utils import features, scenarios
from utils.interfaces._feature_flag_telemetry import metric_points_from_data


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
