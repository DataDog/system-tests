import json
from pathlib import Path
import time

from utils import scenarios, interfaces, logger, features, bug

# Note that an extra comma was added because there is an inconsistency in the postgres metadata compared to what gets sent
postgresql_metrics = {
    "postgresql.connection.max": {
        "data_type": "Gauge",
        "description": "Configured maximum number of client connections allowed",
    },
    "postgresql.database.count": {"data_type": "Sum", "description": "Number of user databases"},
    "postgresql.commits": {"data_type": "Sum", "description": "The number of commits"},
    "postgresql.rollbacks": {"data_type": "Sum", "description": "The number of rollbacks"},
    "postgresql.db_size": {"data_type": "Sum", "description": "The database disk usage"},
    "postgresql.table.count": {"data_type": "Sum", "description": "Number of user tables in a database"},
    # TODO: Those may have been observed somewhere
    # "postgresql.backends": {"data_type": "Sum", "description": "The number of backends"},  TODO
    # "postgresql.table.size": {"data_type": "Sum", "description": "Disk space used by a table"}, TODO
    # "postgresql.rows": {"data_type": "Sum", "description": "The number of rows in the database"},  TODO
    # "postgresql.operations": {"data_type": "Sum", "description": "The number of db row operations"},  TODO
    # "postgresql.index.scans": {"data_type": "Sum", "description": "The number of index scans on a table"}, TODO
    # "postgresql.index.size": {"data_type": "Gauge", "description": "The size of the index on disk"}, TODO
    # "postgresql.blocks_read": {"data_type": "Sum", "description": "The number of blocks read"},  TODO
    # "postgresql.table.vacuum.count": {
    #     "data_type": "Sum",
    #     "description": "Number of times a table has manually been vacuumed",
    # }, TODO
    # "postgresql.bgwriter.buffers.allocated": {"data_type": "Sum", "description": "Number of buffers allocated"}, TODO
    # "postgresql.bgwriter.buffers.writes": {"data_type": "Sum", "description": "Number of buffers written"},TODO
    # "postgresql.bgwriter.checkpoint.count": {"data_type": "Sum", "description": "The number of checkpoints performed"},TODO
    # "postgresql.bgwriter.duration": {
    #     "data_type": "Sum",
    #     "description": "Total time spent writing and syncing files to disk by checkpoints",
    # },TODO
    # "postgresql.bgwriter.maxwritten": {
    #     "data_type": "Sum",
    #     "description": "Number of times the background writer stopped a cleaning scan because it had written too many buffers",
    # }, TODO
    # missing metrics
    # "postgresql.replication.data_delay": {"data_type": "Gauge", "description": "The amount of data delayed in replication"},
    # "postgresql.wal.age": {"data_type": "Gauge", "description": "Age of the oldest WAL file"},
    # "postgresql.wal.lag": {"data_type": "Gauge", "description": "Time between flushing recent WAL locally and receiving notification"},
    # optional metrics
    # "postgresql.blks_hit": {"data_type": "Sum", "description": "Number of times disk blocks were found already in the buffer cache"},
    # "postgresql.blks_read": {"data_type": "Sum", "description": "Number of disk blocks read in this database"},
    # "postgresql.database.locks": {"data_type": "Gauge", "description": "The number of database locks"},
    # "postgresql.deadlocks": {"data_type": "Sum", "description": "The number of deadlocks"},
    # "postgresql.function.calls": {"data_type": "Sum", "description": "The number of calls made to a function. Requires track_functions=pl|all in Postgres config"},
    # "postgresql.sequential_scans": {"data_type": "Sum", "description": "The number of sequential scans"},
    # "postgresql.temp.io": {"data_type": "Sum", "description": "Total amount of data written to temporary files by queries"},
    # "postgresql.temp_files": {"data_type": "Sum", "description": "The number of temp files"},
    # "postgresql.tup_deleted": {"data_type": "Sum", "description": "Number of rows deleted by queries in the database"},
    # "postgresql.tup_fetched": {"data_type": "Sum", "description": "Number of rows fetched by queries in the database"},
    # "postgresql.tup_inserted": {"data_type": "Sum", "description": "Number of rows inserted by queries in the database"},
    # "postgresql.tup_returned": {"data_type": "Sum", "description": "Number of rows returned by queries in the database"},
    # "postgresql.tup_updated": {"data_type": "Sum", "description": "Number of rows updated by queries in the database"},
    # "postgresql.wal.delay": {"data_type": "Gauge", "description": "Time between flushing recent WAL locally and receiving notification that the standby server has completed an operation with it"}
}


def _get_metrics() -> list[dict]:
    collector_log_path = f"{scenarios.otel_collector.collector_container.log_folder_path}/logs/metrics.json"
    assert Path(collector_log_path).exists(), f"Metrics log file not found: {collector_log_path}"

    # Default behaviors is that metrics are batched together in the file exporter
    metrics_batch = []
    with open(collector_log_path, "r", encoding="utf-8") as f:
        for row in f:
            if row.strip():
                metrics_batch.append(json.loads(row.strip()))

    return metrics_batch


@scenarios.otel_collector
@features.otel_postgres_support
class Test_PostgreSQLMetricsCollection:
    def _process_metrics_data(self, data: dict, found_metrics: set[str], metrics_dont_match_spec: set[str]) -> None:
        if "resourceMetrics" not in data:
            return

        for resource_metric in data["resourceMetrics"]:
            self._process_resource_metric(resource_metric, found_metrics, metrics_dont_match_spec)

    def _process_resource_metric(
        self, resource_metric: dict, found_metrics: set[str], metrics_dont_match_spec: set[str]
    ) -> None:
        if "scopeMetrics" not in resource_metric:
            return

        for scope_metric in resource_metric["scopeMetrics"]:
            self._process_scope_metric(scope_metric, found_metrics, metrics_dont_match_spec)

    def _process_scope_metric(
        self, scope_metric: dict, found_metrics: set[str], metrics_dont_match_spec: set[str]
    ) -> None:
        if "metrics" not in scope_metric:
            return

        for metric in scope_metric["metrics"]:
            self._process_individual_metric(metric, found_metrics, metrics_dont_match_spec)

    def _process_individual_metric(
        self, metric: dict, found_metrics: set[str], metrics_dont_match_spec: set[str]
    ) -> None:
        if "name" not in metric:
            return

        metric_name = metric["name"]
        found_metrics.add(metric_name)

        # Skip validation if metric is not in our expected list
        if metric_name not in postgresql_metrics:
            return

        self._validate_metric_specification(metric, metrics_dont_match_spec)

    def _validate_metric_specification(self, metric: dict, metrics_dont_match_spec: set[str]) -> None:
        """Validate that a metric matches its expected specification."""
        metric_name = metric["name"]
        description = metric["description"]
        gauge_type = "gauge" in metric
        sum_type = "sum" in metric

        expected_spec = postgresql_metrics[metric_name]
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

    def test_postgresql_metrics_received_by_collector(self):
        """The goal of this test is to validate that the metrics appear in the Otel Collector logs."""

        metrics_batch = _get_metrics()
        found_metrics: set[str] = set()
        metrics_dont_match_spec: set[str] = set()

        for data in metrics_batch:
            self._process_metrics_data(data, found_metrics, metrics_dont_match_spec)

        validation_results = []
        failed_validations = []

        # As a last check, make sure that ALL metrics in the expected list show up in the logs
        for metric_name in postgresql_metrics:
            if metric_name in found_metrics:
                result = f"✅ {metric_name}"
                validation_results.append(result)
            else:
                result = f"❌ {metric_name}"
                validation_results.append(result)
                failed_validations.append(result)

        # A metric can fail different parts of the spec
        for spec_mismatch in metrics_dont_match_spec:
            failed_validations.append(f"❌ Spec mismatch: {spec_mismatch}")
            validation_results.append(f"❌ Spec mismatch: {spec_mismatch}")

        assert len(failed_validations) == 0, (
            f"Error: {len(failed_validations)} metrics failed the expected behavior!\n"
            f"\n\nFailed validations:\n" + "\n".join(failed_validations)
        )


@scenarios.otel_collector
@features.otel_postgres_support
class Test_BackendValidity:
    def test_postgresql_metrics_received_by_backend(self):
        """The goal of this test is to validate that the metrics can actually be queried, meaning they
        were actually received by the backend.
        """
        lookback_time = 300
        end_time = int(time.time())
        start_time = end_time - lookback_time

        metrics_to_validate = list(postgresql_metrics.keys())

        validated_metrics = []
        failed_metrics = []

        for metric_name in metrics_to_validate:
            logger.info(f"Looking at metric: {metric_name}")
            try:
                start_time_ms = start_time * 1000
                end_time_ms = end_time * 1000

                metric_data = interfaces.backend.query_ui_timeseries(
                    query=f"avg:{metric_name}{{rid:otel-postgres-metrics,host:collector}}",
                    start=start_time_ms,
                    end=end_time_ms,
                    semantic_mode="combined",
                    retries=3,
                    initial_delay_s=15.0,
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
                failed_metrics.append(f"❌  {metric_name}: Failed to query - {e!s}")

        if failed_metrics:
            logger.error(f"\n❌ Failed validations: {failed_metrics}")


@bug(condition=True, reason="AIDM-147", force_skip=False)
@scenarios.otel_collector
@features.otel_postgres_support
class Test_Smoke:
    def setup_main(self):
        container = scenarios.otel_collector.postgres_container
        r = container.exec_run('psql -U system_tests_user -d system_tests_dbname -c "SELECT 1;"')
        logger.info(r.output)

    def test_main(self):
        observed_metrics: set[str] = set()

        expected_metrics = {
            "postgresql.commits",
            "postgresql.connection.max",
            "postgresql.database.count",
            "postgresql.db_size",
            "postgresql.rollbacks",
            "postgresql.table.count",
        }

        for data in interfaces.otel_collector.get_data("/api/v2/series"):
            logger.info(f"In request {data['log_filename']}")
            payload = data["request"]["content"]
            for serie in payload["series"]:
                metric = serie["metric"]
                observed_metrics.add(metric)
                logger.info(f"    {metric} {serie['points']}")

        all_metric_has_be_seen = True
        for metric in expected_metrics:
            if metric not in observed_metrics:
                logger.error(f"Metric {metric} hasn't been observed")
                all_metric_has_be_seen = False
            else:
                logger.error(f"Metric {metric} has been observed")

        assert all_metric_has_be_seen
