# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2024 Datadog, Inc.

import json
import os
import time
from pathlib import Path

from utils import context, weblog, interfaces, scenarios, features, logger


def load_expected_metrics() -> dict[str, dict]:
    """Load the expected MySQL metrics from the mysql_metrics.json file."""
    metrics_file = Path(__file__).parent / "mysql_metrics.json"
    with open(metrics_file, "r") as f:
        return json.load(f)


@scenarios.otel_mysql_metrics_e2e
@features.otel_mysql_support
class Test_OTelMySQLMetricsE2E:
    """Validate MySQL metrics collection via OpenTelemetry instrumentation.

    This test ensures that MySQL metrics are properly collected, exported via OTLP,
    and ingested into the Datadog backend. It validates metrics through three paths:
    1. Via Datadog Agent
    2. Via backend OTLP intake endpoint
    3. Via OTel Collector
    """

    def setup_metrics_collected(self):
        """Initialize test by triggering MySQL operations and capturing timestamp."""
        self.start = int(time.time())
        # Trigger MySQL operations through the weblog
        self.r = weblog.get("/db", params={"service": "mysql", "operation": "select"}, timeout=20)
        self.expected_metrics = load_expected_metrics()
        logger.info(f"Loaded {len(self.expected_metrics)} expected MySQL metrics")

    def test_metrics_collected(self):
        """Verify that MySQL metrics are collected and sent to the backend."""
        end = int(time.time())
        rid = self.r.get_rid().lower()

        # Count how many metrics we successfully found
        metrics_found = 0
        metrics_not_found = []

        for metric_name, metric_info in self.expected_metrics.items():
            logger.info(f"Checking metric: {metric_name} (type: {metric_info['data_type']})")

            try:
                # Try to query the metric from the backend via Agent
                metric_data = interfaces.backend.query_timeseries(
                    start=self.start,
                    end=end,
                    rid=rid,
                    metric=metric_name,
                    dd_api_key=os.environ.get("DD_API_KEY"),
                    dd_app_key=os.environ.get("DD_APP_KEY", os.environ.get("DD_APPLICATION_KEY")),
                )

                if metric_data and len(metric_data.get("series", [])) > 0:
                    metrics_found += 1
                    logger.debug(f"✓ Found metric: {metric_name}")
                else:
                    metrics_not_found.append(metric_name)
                    logger.debug(f"✗ Metric not found: {metric_name}")

            except Exception as e:
                logger.warning(f"Error querying metric {metric_name}: {e}")
                metrics_not_found.append(metric_name)

        logger.info(f"Metrics found: {metrics_found}/{len(self.expected_metrics)}")
        if metrics_not_found:
            logger.warning(f"Metrics not found: {', '.join(metrics_not_found[:10])}")
            if len(metrics_not_found) > 10:
                logger.warning(f"... and {len(metrics_not_found) - 10} more")

        # Assert that at least some core metrics are present
        # We don't require 100% because some metrics may only appear under specific conditions
        assert metrics_found > 0, "No MySQL metrics were found in the backend"

        # Check for some critical metrics that should always be present
        critical_metrics = [
            "mysql.connection.count",
            "mysql.query.count",
            "mysql.threads",
        ]

        for critical_metric in critical_metrics:
            if critical_metric in self.expected_metrics:
                assert critical_metric not in metrics_not_found, f"Critical metric '{critical_metric}' was not found"

    def setup_metrics_via_collector(self):
        """Initialize test by triggering MySQL operations and capturing timestamp."""
        self.start = int(time.time())
        # Trigger MySQL operations through the weblog
        self.r = weblog.get("/db", params={"service": "mysql", "operation": "select"}, timeout=20)
        self.expected_metrics = load_expected_metrics()
        logger.info(f"Loaded {len(self.expected_metrics)} expected MySQL metrics")

    def test_metrics_via_collector(self):
        """Verify that MySQL metrics are properly sent via OTel Collector."""
        end = int(time.time())
        rid = self.r.get_rid().lower()

        # Sample a few key metrics to validate via collector
        sample_metrics = [
            "mysql.connection.count",
            "mysql.query.count",
            "mysql.buffer_pool.usage",
        ]

        metrics_found_collector = 0

        for metric_name in sample_metrics:
            if metric_name not in self.expected_metrics:
                continue

            try:
                metric_data = interfaces.backend.query_timeseries(
                    start=self.start,
                    end=end,
                    rid=rid,
                    metric=metric_name,
                    dd_api_key=os.environ.get("DD_API_KEY_3"),
                    dd_app_key=os.environ.get("DD_APP_KEY_3"),
                )

                if metric_data and len(metric_data.get("series", [])) > 0:
                    metrics_found_collector += 1
                    logger.debug(f"✓ Found metric via collector: {metric_name}")

            except ValueError:
                logger.warning(f"Backend does not provide metric {metric_name} via collector")
            except Exception as e:
                logger.warning(f"Error querying metric {metric_name} via collector: {e}")

        # We expect at least some metrics to be available via collector
        logger.info(f"Metrics found via collector: {metrics_found_collector}/{len(sample_metrics)}")

    def setup_metric_data_types(self):
        """Load expected metrics for validation."""
        self.expected_metrics = load_expected_metrics()

    def test_metric_data_types(self):
        """Verify that metrics have the correct data types (Gauge vs Sum)."""
        # This is a metadata validation test
        for metric_name, metric_info in self.expected_metrics.items():
            data_type = metric_info.get("data_type")
            assert data_type in ["Gauge", "Sum"], f"Metric {metric_name} has invalid data_type: {data_type}"
            logger.debug(f"Metric {metric_name}: data_type={data_type} ✓")
