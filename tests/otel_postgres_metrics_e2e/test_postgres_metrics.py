import os
import re
import time
import json
from datetime import datetime
from utils import context, scenarios, interfaces

# Note that an extra comma was added because there is an inconsistency in the postgres metadata compared to what gets sent
POSTGRESQL_METRICS = {
    "postgresql.connection.max": {"data_type": "Gauge", "description": "Configured maximum number of client connections allowed"},
    "postgresql.database.count": {"data_type": "Sum", "description": "Number of user databases"},
    "postgresql.backends": {"data_type": "Sum", "description": "The number of backends"},
    "postgresql.commits": {"data_type": "Sum", "description": "The number of commits"},
    "postgresql.rollbacks": {"data_type": "Sum", "description": "The number of rollbacks"},
    "postgresql.db_size": {"data_type": "Sum", "description": "The database disk usage"},
    "postgresql.table.size": {"data_type": "Sum", "description": "Disk space used by a table"},
    "postgresql.table.count": {"data_type": "Sum", "description": "Number of user tables in a database"},
    "postgresql.rows": {"data_type": "Sum", "description": "The number of rows in the database"},
    "postgresql.operations": {"data_type": "Sum", "description": "The number of db row operations"},
    "postgresql.index.scans": {"data_type": "Sum", "description": "The number of index scans on a table"},
    "postgresql.index.size": {"data_type": "Gauge", "description": "The size of the index on disk"},
    "postgresql.blocks_read": {"data_type": "Sum", "description": "The number of blocks read"},
    "postgresql.table.vacuum.count": {"data_type": "Sum", "description": "Number of times a table has manually been vacuumed"},
    "postgresql.bgwriter.buffers.allocated": {"data_type": "Sum", "description": "Number of buffers allocated"},
    "postgresql.bgwriter.buffers.writes": {"data_type": "Sum", "description": "Number of buffers written"},
    "postgresql.bgwriter.checkpoint.count": {"data_type": "Sum", "description": "The number of checkpoints performed"},
    "postgresql.bgwriter.duration": {"data_type": "Sum", "description": "Total time spent writing and syncing files to disk by checkpoints"},
    "postgresql.bgwriter.maxwritten": {"data_type": "Sum", "description": "Number of times the background writer stopped a cleaning scan because it had written too many buffers"},
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

@scenarios.otel_postgres_metrics_e2e
class Test_PostgreSQLMetricsCollection:

    def test_postgresql_metrics_received_by_collector(self):
        """
        The goal of this test is to validate that the metrics appear in the Otel Collector logs.
        """
        collector_log_path = f"{context.scenario.host_log_folder}/interfaces/collector/metrics.json"
        assert os.path.exists(collector_log_path), f"Metrics log file not found: {collector_log_path}"

        # Default behaviors is that metrics are batched together in the file exporter
        metrics_batch = []
        with open(collector_log_path, 'r', encoding='utf-8') as f:
            for row in f:
                if row.strip():
                    metrics_batch.append(json.loads(row.strip()))

        found_metrics = set()
        metrics_dont_match_spec = set()
        for data in metrics_batch:
            if "resourceMetrics" in data:
                for resource_metric in data["resourceMetrics"]:
                    if "scopeMetrics" in resource_metric:
                        for scope_metric in resource_metric["scopeMetrics"]:
                            if "metrics" in scope_metric:
                                for metric in scope_metric["metrics"]:
                                    if "name" in metric:
                                        found_metrics.add(metric["name"])


                                        # For metrics we do find, check payload is expected
                                        description = metric["description"]
                                        gauge_type = 'gauge' in metric.keys()
                                        sum_type = 'sum' in metric.keys()

                                        expected_type = POSTGRESQL_METRICS[metric["name"]]['data_type'].lower()
                                        expected_description = POSTGRESQL_METRICS[metric["name"]]['description']

                                        if expected_type == 'sum':
                                            if not sum_type:
                                                metrics_dont_match_spec.add(f"{metric['name']}: Expected Sum type but got Gauge")
                                        elif expected_type == 'gauge':
                                            if not gauge_type:
                                                metrics_dont_match_spec.add(f"{metric['name']}: Expected Gauge type but got Sum")

                                        # Sometimes the spec has a period, but the actual logs don't.
                                        if description.rstrip('.') != expected_description.rstrip('.'):
                                            metrics_dont_match_spec.add(f"{metric['name']}: Description mismatch - Expected: '{expected_description}', Got: '{description}'")



        validation_results = []
        failed_validations = []

        # As a last check, make sure that ALL metrics in the expected list show up in the logs
        for metric_name, specs in POSTGRESQL_METRICS.items():
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

    def test_postgresql_metrics_received_by_backend(self):
        """
        The goal of this test is to validate that the metrics can actually be queried, meaning they
        were actually received by the backend.
        """
        lookback_time = 300
        end_time = int(time.time())
        start_time = end_time - lookback_time

        metrics_to_validate = list(POSTGRESQL_METRICS.keys())

        validated_metrics = []
        failed_metrics = []

        for metric_name in metrics_to_validate:
            try:
                metric_data = interfaces.backend.query_timeseries(
                    rid="otel-postgres-metrics,host:collector", #TODO: figure out if this needs to be dynamic
                    start=start_time,
                    end=end_time,
                    metric=metric_name,
                    retries=3,
                    initial_delay_s=15.0
                )

                if metric_data and "series" in metric_data and len(metric_data["series"]) > 0:
                    series = metric_data["series"][0]
                    if "pointlist" in series and len(series["pointlist"]) > 0:
                        validated_metrics.append(metric_name)
                    else:
                        failed_metrics.append(f"{metric_name}: No data points found")
                else:
                    failed_metrics.append(f"{metric_name}: No series data returned")

            except Exception as e:
                failed_metrics.append(f"❌  {metric_name}: Failed to query - {str(e)}")

        if failed_metrics:
            print(f"\n❌ Failed validations: {failed_metrics}")

