import time
from pathlib import Path
from typing import TYPE_CHECKING

from utils import scenarios, interfaces, logger, features, context
from utils.otel_validators.validator_metrics import OtelMetricsValidator, get_collector_metrics_from_scenario

if TYPE_CHECKING:
    from utils._context._scenarios.otel_collector import OtelCollectorScenario


# Load PostgreSQL metrics specification
# Exclude metrics that require a replica database
_EXCLUDED_POSTGRES_METRICS = {
    "postgresql.wal.delay",  # requires replica
    "postgresql.wal.age",  # requires replica
    "postgresql.replication.data_delay",  # requires replica
    "postgresql.wal.lag",  # requires replica
}

postgresql_metrics = OtelMetricsValidator.load_metrics_from_file(
    metrics_file=Path(__file__).parent / "postgres_metrics.json",
    excluded_metrics=_EXCLUDED_POSTGRES_METRICS,
)

# Initialize validator with PostgreSQL metrics
_metrics_validator = OtelMetricsValidator(postgresql_metrics)


@scenarios.otel_collector
@scenarios.otel_collector_e2e
@features.postgres_receiver_metrics
class Test_PostgreSQLMetricsCollection:
    def test_postgresql_metrics_received_by_collector(self):
        scenario: OtelCollectorScenario = context.scenario  # type: ignore[assignment]
        metrics_batch = get_collector_metrics_from_scenario(scenario)

        _, _, _validation_results, failed_validations = _metrics_validator.process_and_validate_metrics(metrics_batch)

        assert len(failed_validations) == 0, (
            f"Error: {len(failed_validations)} metrics failed the expected behavior!\n"
            f"\n\nFailed validations:\n" + "\n".join(failed_validations)
        )


@scenarios.otel_collector_e2e
@features.postgres_receiver_metrics
class Test_BackendValidity:
    def test_postgresql_metrics_received_by_backend(self):
        """Test metrics were actually queried / received by the backend"""
        metrics_to_validate = list(postgresql_metrics.keys())
        query_tags = {"rid": "otel-postgres-metrics", "host": "collector"}

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


@scenarios.otel_collector
@scenarios.otel_collector_e2e
@features.postgres_receiver_metrics
class Test_Smoke:
    """PostgreSQL-specific smoke test to generate database activity.
    This test validates that basic PostgreSQL metrics are collected after database operations.
    """

    def setup_main(self) -> None:
        """When the postgres container spins up, we need some activity:
        - call a test function
        - create a table
        - query something
        """
        scenario: OtelCollectorScenario = context.scenario  # type: ignore[assignment]
        container = scenario.postgres_container

        r = container.exec_run(
            "psql -U system_tests_user -d system_tests_dbname -c "
            '"CREATE OR REPLACE FUNCTION test_return_1_function() RETURNS integer AS $$ BEGIN RETURN 1; END; $$ LANGUAGE plpgsql;"'
        )
        r = container.exec_run('psql -U system_tests_user -d system_tests_dbname -c "SELECT test_return_1_function();"')
        logger.info(r.output)

        r = container.exec_run(
            "psql -U system_tests_user -d system_tests_dbname -c "
            '"CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY);"'
        )

        r = container.exec_run(
            'psql -U system_tests_user -d system_tests_dbname -c "INSERT INTO test_table DEFAULT VALUES;"'
        )

        r = container.exec_run('psql -U system_tests_user -d system_tests_dbname -c "SELECT 1;"')

        # Rollback
        r = container.exec_run(
            'psql -U system_tests_user -d system_tests_dbname -c "BEGIN; INSERT INTO test_table DEFAULT VALUES; ROLLBACK;"'
        )

        # Vacuums and forces a read block (FULL activates the blocks_read metric)
        r = container.exec_run('psql -U system_tests_user -d system_tests_dbname -c "VACUUM FULL test_table;"')
        r = container.exec_run('psql -U system_tests_user -d system_tests_dbname -c "VACUUM test_table;"')

        # Forces an index scan with the two sets of psql commands
        r = container.exec_run(
            "psql -U system_tests_user -d system_tests_dbname -c "
            '"INSERT INTO test_table DEFAULT VALUES FROM generate_series(1, 800);"'
        )

        r = container.exec_run(
            "psql -U system_tests_user -d system_tests_dbname -c "
            '"SET enable_seqscan = off; SET enable_bitmapscan = off; '
            'SELECT * FROM test_table WHERE id = 300;"'
        )

        # Forces temp files for postgresql.temp.io and postgresql.temp_files
        r = container.exec_run(
            "psql -U system_tests_user -d system_tests_dbname -c "
            "\"SET work_mem = '64kB'; "
            'SELECT * FROM generate_series(1, 1000000) g ORDER BY g;"'
        )

        # hit the buffer + max writtern
        r = container.exec_run(
            'psql -U system_tests_user -d system_tests_dbname -c "'
            "CREATE TABLE IF NOT EXISTS bg_test AS "
            "SELECT i, md5(random()::text) FROM generate_series(1, 2000000) g(i); "
            "UPDATE bg_test SET i = i + 1; "
            "UPDATE bg_test SET i = i + 1; "
            'SELECT pg_sleep(2);"'
        )

        logger.info(r.output)

    def test_main(self) -> None:
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
                logger.info(f"Metric {metric} has been observed")

        assert all_metric_has_be_seen
