import os
import re
from utils import context, scenarios


@scenarios.otel_postgres_metrics_e2e
class Test_PostgreSQLMetricsCollection:

    def test_postgresql_metrics_comprehensive_validation(self):
        collector_log_path = f"{context.scenario.host_log_folder}/docker/collector/stderr.log"
        assert os.path.exists(collector_log_path), f"Collector log file not found: {collector_log_path}"

        with open(collector_log_path, 'r', encoding='utf-8') as f:
            log_content = f.read()

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
            # missing metrics
            # "postgresql.bgwriter.buffers.allocated": {"data_type": "Sum", "description": "Number of buffers allocated"},
            # "postgresql.bgwriter.buffers.writes": {"data_type": "Sum", "description": "Number of buffers written"},
            # "postgresql.bgwriter.checkpoint.count": {"data_type": "Sum", "description": "The number of checkpoints performed"},
            # "postgresql.bgwriter.duration": {"data_type": "Sum", "description": "Total time spent writing and syncing files to disk by checkpoints"},
            # "postgresql.bgwriter.maxwritten": {"data_type": "Sum", "description": "Number of times the background writer stopped a cleaning scan"},
            # "postgresql.replication.data_delay": {"data_type": "Gauge", "description": "The amount of data delayed in replication"},
            # "postgresql.wal.age": {"data_type": "Gauge", "description": "Age of the oldest WAL file"},
            # "postgresql.wal.lag": {"data_type": "Gauge", "description": "Time between flushing recent WAL locally and receiving notification"}
        }
        
        collected_metrics = list(POSTGRESQL_METRICS.keys())
        
        all_expected_metrics = collected_metrics

        missing_metrics = []
        found_metrics = []
        
        for metric in all_expected_metrics:
            if metric in log_content:
                found_metrics.append(metric)
            else:
                missing_metrics.append(metric)
        
        assert len(missing_metrics) == 0, (
            f"Integration metrics are missing from collector logs! "
            f"Missing: {missing_metrics}. "
            f"Found: {found_metrics}. "
            f"Expected ALL {len(all_expected_metrics)} metrics to be present."
        )

        required_metric_patterns = {}
        for metric_name, specs in POSTGRESQL_METRICS.items():
            required_metric_patterns[metric_name] = {
                "data_type": specs["data_type"],
                "value_pattern": r"Value: \d+",
                "min_occurrences": 1,
                "description": specs["description"]
            }

        validation_results = []
        failed_validations = []
        
        for metric_name, requirements in required_metric_patterns.items():
            metric_pattern = rf"-> Name: {re.escape(metric_name)}.*?-> DataType: {requirements['data_type']}.*?{requirements['value_pattern']}"
            matches = re.findall(metric_pattern, log_content, re.DOTALL)
            
            found_count = len(matches)
            min_required = requirements['min_occurrences']
            description = requirements['description']
            
            if found_count >= min_required:
                result = f"✅ {metric_name}: {found_count} occurrences (≥{min_required} required) - {description}"
                validation_results.append(result)
            else:
                result = f"❌ {metric_name}: {found_count} occurrences (<{min_required} required) - {description}"
                validation_results.append(result)
                failed_validations.append(result)

        assert len(failed_validations) == 0, (
            f"CRITICAL: {len(failed_validations)} metrics failed detailed validation!\n"
            f"Failures:\n" + "\n".join(failed_validations) + 
            f"\n\nAll detailed validations:\n" + "\n".join(validation_results)
        )

    
    def test_metrics_export_to_datadog(self):

        collector_log_path = f"{context.scenario.host_log_folder}/docker/collector/stderr.log"
        
        with open(collector_log_path, 'r', encoding='utf-8') as f:
            log_content = f.read()

        datadog_patterns = [
            '"kind": "exporter"',
            '"name": "datadog"',
            '"data_type": "metrics"'
        ]
        
        for pattern in datadog_patterns:
            assert pattern in log_content, f"Datadog exporter pattern '{pattern}' not found"
