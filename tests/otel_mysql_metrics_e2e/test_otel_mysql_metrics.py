import time
from pathlib import Path
from typing import TYPE_CHECKING

from utils import scenarios, interfaces, logger, features, context
from utils.otel_metrics_validator import OtelMetricsValidator, get_collector_metrics_from_scenario

if TYPE_CHECKING:
    from utils._context._scenarios.otel_collector import OtelCollectorScenario


# Load MySQL metrics specification
# Exclude metrics that require specific configurations or sustained activity
_EXCLUDED_MYSQL_METRICS: set[str] = set()
# Add any metrics that need to be excluded here
# Example: metrics that require replication, specific storage engines, etc.

mysql_metrics = OtelMetricsValidator.load_metrics_from_file(
    metrics_file=Path(__file__).parent / "mysql_metrics.json",
    excluded_metrics=_EXCLUDED_MYSQL_METRICS,
)

# Initialize validator with MySQL metrics
_metrics_validator = OtelMetricsValidator(mysql_metrics)


@scenarios.otel_mysql_metrics_e2e
@features.otel_mysql_support
class Test_MySQLMetricsCollection:
    def test_mysql_metrics_received_by_collector(self):
        scenario: OtelCollectorScenario = context.scenario  # type: ignore[assignment]
        metrics_batch = get_collector_metrics_from_scenario(scenario)

        _, _, _validation_results, failed_validations = _metrics_validator.process_and_validate_metrics(metrics_batch)

        assert len(failed_validations) == 0, (
            f"Error: {len(failed_validations)} metrics failed the expected behavior!\n"
            f"\n\nFailed validations:\n" + "\n".join(failed_validations)
        )


@scenarios.otel_mysql_metrics_e2e
@features.otel_mysql_support
class Test_BackendValidity:
    def test_mysql_metrics_received_by_backend(self):
        """Test metrics were actually queried / received by the backend"""
        metrics_to_validate = list(mysql_metrics.keys())
        query_tags = {"rid": "otel-mysql-metrics", "host": "collector"}

        time.sleep(15)
        _validated_metrics, failed_metrics = _metrics_validator.query_backend_for_metrics(
            metric_names=metrics_to_validate,
            query_tags=query_tags,
            lookback_seconds=300,
            retries=3,
            initial_delay_s=0.5,
            semantic_mode="combined",
        )

        if failed_metrics:
            logger.error(f"\n❌ Failed validations for semantic mode combined: {failed_metrics}")

        # test with native mode
        _validated_metrics, failed_metrics = _metrics_validator.query_backend_for_metrics(
            metric_names=metrics_to_validate,
            query_tags=query_tags,
            lookback_seconds=300,
            retries=3,
            initial_delay_s=0.5,
            semantic_mode="native",
        )

        if failed_metrics:
            logger.error(f"\n❌ Failed validations for semantic mode native: {failed_metrics}")


@scenarios.otel_mysql_metrics_e2e
@features.otel_mysql_support
class Test_Smoke:
    """MySQL-specific smoke test to generate database activity.
    This test validates that basic MySQL metrics are collected after database operations.
    """

    def setup_main(self) -> None:
        """When the MySQL container spins up, we need some activity:
        - create a table
        - insert some data
        - run queries
        """
        scenario: OtelCollectorScenario = context.scenario  # type: ignore[assignment]
        container = scenario.mysql_container

        # Create table
        r = container.exec_run(
            "mysql -u system_tests_user -psystem_tests_password system_tests_dbname -e "
            '"CREATE TABLE IF NOT EXISTS test_table (id INT PRIMARY KEY AUTO_INCREMENT, value VARCHAR(255));"'
        )
        logger.info(f"Create table output: {r.output}")

        # Insert data
        r = container.exec_run(
            "mysql -u system_tests_user -psystem_tests_password system_tests_dbname -e "
            "\"INSERT INTO test_table (value) VALUES ('test1'), ('test2'), ('test3');\""
        )
        logger.info(f"Insert data output: {r.output}")

        # Run a SELECT query
        r = container.exec_run(
            'mysql -u system_tests_user -psystem_tests_password system_tests_dbname -e "SELECT * FROM test_table;"'
        )
        logger.info(f"Select query output: {r.output}")

        # Run a COUNT query
        r = container.exec_run(
            "mysql -u system_tests_user -psystem_tests_password system_tests_dbname -e "
            '"SELECT COUNT(*) FROM test_table;"'
        )
        logger.info(f"Count query output: {r.output}")

    def test_main(self) -> None:
        observed_metrics: set[str] = set()

        expected_metrics = {
            "mysql.buffer_pool.usage",
            "mysql.connection.count",
            "mysql.connection.errors",
            "mysql.query.count",
            "mysql.threads",
        }

        for data in interfaces.otel_collector.get_data("/api/v2/series"):
            logger.info(f"In request {data['log_filename']}")
            payload = data["request"]["content"]
            for serie in payload["series"]:
                metric = serie["metric"]
                observed_metrics.add(metric)
                logger.info(f"    {metric} {serie['points']}")

        for metric in expected_metrics:
            if metric not in observed_metrics:
                logger.error(f"Metric {metric} hasn't been observed")
            else:
                logger.info(f"Metric {metric} has been observed")
