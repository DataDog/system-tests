import os
import re
import time
import json
from datetime import datetime
from utils import context, scenarios, interfaces

# Note that an extra comma was added because there is an inconsistency in the mysql metadata compared to what gets sent
MYSQL_METRICS = {
 "mysql.buffer_pool.pages": {
  "data_type": "Unknown",
  "description": "The number of pages in the InnoDB buffer pool."
 },
 "mysql.buffer_pool.data_pages": {
  "data_type": "Unknown",
  "description": "The number of data pages in the InnoDB buffer pool."
 },
 "mysql.buffer_pool.page_flushes": {
  "data_type": "Counter",
  "description": "The number of requests to flush pages from the InnoDB buffer pool."
 },
 "mysql.buffer_pool.operations": {
  "data_type": "Counter",
  "description": "The number of operations on the InnoDB buffer pool."
 },
#  "mysql.buffer_pool.limit": {
#   "data_type": "Unknown",
#   "description": "The configured size of the InnoDB buffer pool."
#  },
 "mysql.buffer_pool.usage": {
  "data_type": "Unknown",
  "description": "The number of bytes in the InnoDB buffer pool."
 },
 "mysql.prepared_statements": {
  "data_type": "Counter",
  "description": "The number of times each type of prepared statement command has been issued."
 },
#  "mysql.commands": {
#   "data_type": "Counter",
#   "description": "The number of times each type of command has been executed."
#  },
 "mysql.handlers": {
  "data_type": "Counter",
  "description": "The number of requests to various MySQL handlers."
 },
 "mysql.double_writes": {
  "data_type": "Counter",
  "description": "The number of writes to the InnoDB doublewrite buffer."
 },
 "mysql.log_operations": {
  "data_type": "Counter",
  "description": "The number of InnoDB log operations."
 },
 "mysql.operations": {
  "data_type": "Counter",
  "description": "The number of InnoDB operations."
 },
 "mysql.page_operations": {
  "data_type": "Counter",
  "description": "The number of InnoDB page operations."
 },
#  "mysql.table.io.wait.count": {
#   "data_type": "Counter",
#   "description": "The total count of I/O wait events for a table."
#  },
#  "mysql.table.io.wait.time": {
#   "data_type": "Counter",
#   "description": "The total time of I/O wait events for a table."
#  },
#  "mysql.table.rows": {
#   "data_type": "Unknown",
#   "description": "The number of rows for a given table."
#  },
#  "mysql.table.average_row_length": {
#   "data_type": "Unknown",
#   "description": "The average row length in bytes for a given table."
#  },
#  "mysql.table.size": {
#   "data_type": "Unknown",
#   "description": "The table size in bytes for a given table."
#  },
#  "mysql.index.io.wait.count": {
#   "data_type": "Counter",
#   "description": "The total count of I/O wait events for an index."
#  },
#  "mysql.index.io.wait.time": {
#   "data_type": "Counter",
#   "description": "The total time of I/O wait events for an index."
#  },
 "mysql.row_locks": {
  "data_type": "Counter",
  "description": "The number of InnoDB row locks."
 },
 "mysql.row_operations": {
  "data_type": "Counter",
  "description": "The number of InnoDB row operations."
 },
 "mysql.locks": {
  "data_type": "Counter",
  "description": "The number of MySQL locks."
 },
 "mysql.sorts": {
  "data_type": "Counter",
  "description": "The number of MySQL sorts."
 },
 "mysql.threads": {
  "data_type": "Unknown",
  "description": "The state of MySQL threads."
 },
#  "mysql.client.network.io": {
#   "data_type": "Counter",
#   "description": "The number of transmitted bytes between server and clients."
#  },
 "mysql.opened_resources": {
  "data_type": "Counter",
  "description": "The number of opened resources."
 },
 "mysql.uptime": {
  "data_type": "Counter",
  "description": "The number of seconds that the server has been up."
 },
#  "mysql.table.lock_wait.read.count": {
#   "data_type": "Unknown",
#   "description": "The total table lock wait read events."
#  },
#  "mysql.table.lock_wait.read.time": {
#   "data_type": "Unknown",
#   "description": "The total table lock wait read events times."
#  },
#  "mysql.table.lock_wait.write.count": {
#   "data_type": "Unknown",
#   "description": "The total table lock wait write events."
#  },
#  "mysql.table.lock_wait.write.time": {
#   "data_type": "Unknown",
#   "description": "The total table lock wait write events times."
#  },
#  "mysql.connection.count": {
#   "data_type": "Counter",
#   "description": "The number of connection attempts (successful or not) to the MySQL server."
#  },
#  "mysql.max_used_connections": {
#   "data_type": "Unknown",
#   "description": "Maximum number of connections used simultaneously since the server started."
#  },
#  "mysql.connection.errors": {
#   "data_type": "Counter",
#   "description": "Errors that occur during the client connection process."
#  },
 "mysql.mysqlx_connections": {
  "data_type": "Counter",
  "description": "The number of mysqlx connections."
 },
#  "mysql.joins": {
#   "data_type": "Counter",
#   "description": "The number of joins that perform table scans."
#  },
 "mysql.tmp_resources": {
  "data_type": "Counter",
  "description": "The number of created temporary resources."
 },
#  "mysql.replica.time_behind_source": {
#   "data_type": "Unknown",
#   "description": "This field is an indication of how \u201clate\u201d the replica is."
#  },
#  "mysql.replica.sql_delay": {
#   "data_type": "Unknown",
#   "description": "The number of seconds that the replica must lag the source."
#  },
#  "mysql.statement_event.count": {
#   "data_type": "Unknown",
#   "description": "Summary of current and recent statement events."
#  },
#  "mysql.statement_event.wait.time": {
#   "data_type": "Unknown",
#   "description": "The total wait time of the summarized timed events."
#  },
#  "mysql.mysqlx_worker_threads": {
#   "data_type": "Unknown",
#   "description": "The number of worker threads available."
#  },
#  "mysql.table_open_cache": {
#   "data_type": "Counter",
#   "description": "The number of hits, misses or overflows for open tables cache lookups."
#  },
#  "mysql.query.client.count": {
#   "data_type": "Counter",
#   "description": "The number of statements executed by the server. This includes only statements sent to the server by clients."
#  },
#  "mysql.query.count": {
#   "data_type": "Counter",
#   "description": "The number of statements executed by the server."
#  },
#  "mysql.query.slow.count": {
#   "data_type": "Counter",
#   "description": "The number of slow queries."
#  },
#  "mysql.page_size": {
#   "data_type": "Unknown",
#   "description": "InnoDB page size."
#  }
}

@scenarios.otel_mysql_metrics_e2e
class Test_MySQLMetricsCollection:

    def _process_metrics_data(self, data: dict, found_metrics: set[str], metrics_dont_match_spec: set[str]) -> None:
        if "resourceMetrics" not in data:
            return
            
        for resource_metric in data["resourceMetrics"]:
            self._process_resource_metric(resource_metric, found_metrics, metrics_dont_match_spec)
    
    def _process_resource_metric(self, resource_metric: dict, found_metrics: set[str], metrics_dont_match_spec: set[str]) -> None:
        if "scopeMetrics" not in resource_metric:
            return
            
        for scope_metric in resource_metric["scopeMetrics"]:
            self._process_scope_metric(scope_metric, found_metrics, metrics_dont_match_spec)
    
    def _process_scope_metric(self, scope_metric: dict, found_metrics: set[str], metrics_dont_match_spec: set[str]) -> None:
        if "metrics" not in scope_metric:
            return
            
        for metric in scope_metric["metrics"]:
            self._process_individual_metric(metric, found_metrics, metrics_dont_match_spec)
    
    def _process_individual_metric(self, metric: dict, found_metrics: set[str], metrics_dont_match_spec: set[str]) -> None:
        if "name" not in metric:
            return
            
        metric_name = metric["name"]
        found_metrics.add(metric_name)
        
        # Skip validation if metric is not in our expected list
        if metric_name not in MYSQL_METRICS:
            return
            
        self._validate_metric_specification(metric, metrics_dont_match_spec)
    
    def _validate_metric_specification(self, metric: dict, metrics_dont_match_spec: set[str]) -> None:
        metric_name = metric["name"]
        description = metric["description"]
        gauge_type = 'gauge' in metric.keys()
        sum_type = 'sum' in metric.keys()
        
        expected_spec = MYSQL_METRICS[metric_name]
        expected_type = expected_spec['data_type'].lower()
        expected_description = expected_spec['description']
        
        if expected_type == 'sum' and not sum_type:
            metrics_dont_match_spec.add(f"{metric_name}: Expected Sum type but got Gauge")
        elif expected_type == 'gauge' and not gauge_type:
            metrics_dont_match_spec.add(f"{metric_name}: Expected Gauge type but got Sum")
        
        if description.rstrip('.') != expected_description.rstrip('.'):
            metrics_dont_match_spec.add(
                f"{metric_name}: Description mismatch - Expected: '{expected_description}', Got: '{description}'"
            )

    def test_mysql_metrics_received_by_collector(self):
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

        found_metrics: set[str] = set()
        metrics_dont_match_spec: set[str] = set()
        
        for data in metrics_batch:
            self._process_metrics_data(data, found_metrics, metrics_dont_match_spec)



        validation_results = []
        failed_validations = []

        # As a last check, make sure that ALL metrics in the expected list show up in the logs
        for metric_name, specs in MYSQL_METRICS.items():
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

    def test_mysql_metrics_received_by_backend(self):
        """
        The goal of this test is to validate that the metrics can actually be queried, meaning they
        were actually received by the backend.
        """
        lookback_time = 300
        end_time = int(time.time())
        start_time = end_time - lookback_time

        metrics_to_validate = list(MYSQL_METRICS.keys())

        validated_metrics = []
        failed_metrics = []

        for metric_name in metrics_to_validate:
            try:
                metric_data = interfaces.backend.query_timeseries(
                    rid="otel-mysql-metrics,host:collector", #TODO: figure out if this needs to be dynamic
                    start=start_time,
                    end=end_time,
                    metric=metric_name,
                    retries=3,
                    initial_delay_s=1
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