# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""Validate Feature Flags telemetry after its selected export route."""

from collections.abc import Generator
from typing import Any

from utils.interfaces._core import ProxyBasedInterfaceValidator


class FeatureFlagTelemetryInterfaceValidator(ProxyBasedInterfaceValidator):
    """Capture EVP and metrics with sidecar/direct route provenance."""

    def get_metrics(self) -> Generator[tuple[dict, dict], None, None]:
        """Yield normalized Datadog-series or direct-OTLP metric points."""

        for data in self.get_data(path_filters=("/api/v2/series", "/api/intake/metrics/v3/series", "/v1/metrics")):
            for point in metric_points_from_data(data):
                yield data, point


def metric_points_from_data(data: dict) -> Generator[dict, None, None]:
    content = data.get("request", {}).get("content")
    if not isinstance(content, dict):
        return

    if data.get("path") == "/v1/metrics":
        yield from _get_otlp_metrics(content)
        return

    for point in content.get("series", []):
        if isinstance(point, dict):
            yield point


def _get_otlp_metrics(content: dict) -> Generator[dict, None, None]:
    for resource_metrics in content.get("resourceMetrics", []):
        for scope_metrics in resource_metrics.get("scopeMetrics", []):
            for metric in scope_metrics.get("metrics", []):
                metric_name = metric.get("name")
                if not isinstance(metric_name, str):
                    continue

                metric_data = metric.get("sum") or metric.get("gauge") or {}
                for data_point in metric_data.get("dataPoints", []):
                    tags = []
                    for attribute in data_point.get("attributes", []):
                        key = attribute.get("key")
                        value = _otlp_attribute_value(attribute.get("value"))
                        if isinstance(key, str) and value is not None:
                            tags.append(f"{key}:{value}")

                    yield {"metric": metric_name, "tags": tags, "point": data_point}


def _otlp_attribute_value(value: Any) -> str | None:  # noqa: ANN401
    if not isinstance(value, dict):
        return None

    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return str(value[key]).lower() if key == "boolValue" else str(value[key])

    return None
