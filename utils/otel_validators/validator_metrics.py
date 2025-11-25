"""Utility module for validating OpenTelemetry integration metrics.

This module provides reusable components for testing OTel receiver metrics:
- Loading metric specifications from JSON files
- Retrieving metrics from OTel Collector logs
- Validating metrics against specifications
- Querying metrics from the Datadog backend
"""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from utils import interfaces, logger

if TYPE_CHECKING:
    from utils._context._scenarios.otel_collector import OtelCollectorScenario


class OtelMetricsValidator:
    """Base class for validating OTel integration metrics."""

    def __init__(self, metrics_spec: dict[str, dict[str, str]]) -> None:
        """Initialize the validator with a metrics specification."""
        self.metrics_spec = metrics_spec

    @staticmethod
    def load_metrics_from_file(
        metrics_file: Path, excluded_metrics: set[str] | None = None
    ) -> dict[str, dict[str, str]]:
        """Load metric specifications from a JSON file, excluding excluded_metrics (if provided).
        Return transformed metrics
        """
        if not metrics_file.exists():
            raise FileNotFoundError(f"Metrics file not found: {metrics_file}")

        with open(metrics_file, encoding="utf-8") as f:
            metrics = json.load(f)

        if excluded_metrics:
            return {k: v for k, v in metrics.items() if k not in excluded_metrics}

        return metrics

    @staticmethod
    def get_collector_metrics(collector_log_path: str) -> list[dict[str, Any]]:
        """Retrieve metrics from the OTel Collector's file exporter logs.
        Given path to the collector's metrics log file, returns list of metric batch dictionaries
        """
        assert Path(collector_log_path).exists(), f"Metrics log file not found: {collector_log_path}"

        metrics_batch = []
        with open(collector_log_path, "r", encoding="utf-8") as f:
            for row in f:
                if row.strip():
                    metrics_batch.append(json.loads(row.strip()))

        return metrics_batch

    def process_and_validate_metrics(
        self, metrics_batch: list[dict[str, Any]]
    ) -> tuple[set[str], set[str], list[str], list[str]]:
        """Process metrics batch and validate against specifications from backend.
        Returns (found_metrics, metrics_dont_match_spec, validation_results, failed_validations)
        """
        found_metrics: set[str] = set()
        metrics_dont_match_spec: set[str] = set()

        for data in metrics_batch:
            self._process_metrics_data(data, found_metrics, metrics_dont_match_spec)

        validation_results = []
        failed_validations = []

        # Check that all expected metrics were found
        for metric_name in self.metrics_spec:
            if metric_name in found_metrics:
                result = f"✅ {metric_name}"
                validation_results.append(result)
            else:
                result = f"❌ {metric_name}"
                validation_results.append(result)
                failed_validations.append(result)

        # Add spec mismatches to failures
        for spec_mismatch in metrics_dont_match_spec:
            failed_validations.append(f"❌ Spec mismatch: {spec_mismatch}")
            validation_results.append(f"❌ Spec mismatch: {spec_mismatch}")

        return found_metrics, metrics_dont_match_spec, validation_results, failed_validations

    def _process_metrics_data(
        self, data: dict[str, Any], found_metrics: set[str], metrics_dont_match_spec: set[str]
    ) -> None:
        """Process top-level metrics data structure."""
        if "resourceMetrics" not in data:
            return

        for resource_metric in data["resourceMetrics"]:
            self._process_resource_metric(resource_metric, found_metrics, metrics_dont_match_spec)

    def _process_resource_metric(
        self, resource_metric: dict[str, Any], found_metrics: set[str], metrics_dont_match_spec: set[str]
    ) -> None:
        """Process resource-level metrics."""
        if "scopeMetrics" not in resource_metric:
            return

        for scope_metric in resource_metric["scopeMetrics"]:
            self._process_scope_metric(scope_metric, found_metrics, metrics_dont_match_spec)

    def _process_scope_metric(
        self, scope_metric: dict[str, Any], found_metrics: set[str], metrics_dont_match_spec: set[str]
    ) -> None:
        """Process scope-level metrics."""
        if "metrics" not in scope_metric:
            return

        for metric in scope_metric["metrics"]:
            self._process_individual_metric(metric, found_metrics, metrics_dont_match_spec)

    def _process_individual_metric(
        self, metric: dict[str, Any], found_metrics: set[str], metrics_dont_match_spec: set[str]
    ) -> None:
        """Process and validate individual metric."""
        if "name" not in metric:
            return

        metric_name = metric["name"]
        found_metrics.add(metric_name)

        # Skip validation if metric is not in our expected list
        if metric_name not in self.metrics_spec:
            return

        self._validate_metric_specification(metric, metrics_dont_match_spec)

    def _validate_metric_specification(self, metric: dict[str, Any], metrics_dont_match_spec: set[str]) -> None:
        """Validate that a metric matches its expected specification."""
        metric_name = metric["name"]
        description = metric["description"]
        gauge_type = "gauge" in metric
        sum_type = "sum" in metric

        expected_spec = self.metrics_spec[metric_name]
        expected_type = expected_spec["data_type"].lower()
        expected_description = expected_spec["description"]

        # Validate metric type
        if expected_type == "sum" and not sum_type:
            metrics_dont_match_spec.add(f"{metric_name}: Expected Sum type but got Gauge")
        elif expected_type == "gauge" and not gauge_type:
            metrics_dont_match_spec.add(f"{metric_name}: Expected Gauge type but got Sum")

        # Validate description (sometimes the spec has a period, but the actual logs don't)
        if description.rstrip(".") != expected_description.rstrip("."):
            metrics_dont_match_spec.add(
                f"{metric_name}: Description mismatch - Expected: '{expected_description}', Got: '{description}'"
            )

    def query_backend_for_metrics(
        self,
        metric_names: list[str],
        query_tags: dict[str, str],
        lookback_seconds: int = 300,
        retries: int = 3,
        initial_delay_s: float = 15.0,
        semantic_mode: str = "combined",
    ) -> tuple[list[str], list[str]]:
        """Query the Datadog backend to validate metrics were received.
        Returns (validated_metrics, failed_metrics)
        """
        end_time = int(time.time())
        start_time = end_time - lookback_seconds

        validated_metrics = []
        failed_metrics = []

        # Build tag string for query
        tag_string = ",".join(f"{k}:{v}" for k, v in query_tags.items())

        for metric_name in metric_names:
            logger.info(f"Looking at metric: {metric_name}")
            try:
                start_time_ms = start_time * 1000
                end_time_ms = end_time * 1000

                query_str = f"avg:{metric_name}{{{tag_string}}}"
                logger.info(f"Query: {query_str}, time range: {start_time_ms} to {end_time_ms} ({lookback_seconds}s)")

                metric_data = interfaces.backend.query_ui_timeseries(
                    query=query_str,
                    start=start_time_ms,
                    end=end_time_ms,
                    semantic_mode=semantic_mode,
                    retries=retries,
                    initial_delay_s=initial_delay_s,
                )

                if metric_data and metric_data.get("data") and len(metric_data["data"]) > 0:
                    data_item = metric_data["data"][0]
                    attributes = data_item.get("attributes", {})

                    meta_responses = metric_data.get("meta", {}).get("responses", [])
                    results_warning = meta_responses[0].get("results_warnings") if meta_responses else None
                    if results_warning:
                        logger.warning(f"Results warning: {results_warning}")

                    times = attributes.get("times", [])
                    values = attributes.get("values", [])

                    if times and values and len(values) > 0 and len(values[0]) > 0:
                        validated_metrics.append(metric_name)
                    else:
                        failed_metrics.append(f"{metric_name}: No data points found")
                else:
                    failed_metrics.append(f"{metric_name}: No series data returned")

            except Exception as e:
                failed_metrics.append(f"❌  {metric_name}: Failed to query semantic mode {semantic_mode} - {e!s}")

        return validated_metrics, failed_metrics


def get_collector_metrics_from_scenario(scenario: "OtelCollectorScenario") -> list[dict[str, Any]]:
    """Helper function to get metrics from an OtelCollectorScenario.
    Returns a list of metric batch dictionaries
    """
    collector_log_path = f"{scenario.collector_container.log_folder_path}/logs/metrics.json"
    return OtelMetricsValidator.get_collector_metrics(collector_log_path)
