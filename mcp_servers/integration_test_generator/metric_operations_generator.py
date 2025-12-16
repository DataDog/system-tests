"""Generators for creating metric-specific smoke test operations."""

import json
from pathlib import Path


def generate_postgres_operation(metric_name: str) -> tuple[list[str], bool]:
    """Generate PostgreSQL-specific operation for a metric.

    Returns:
        Tuple of (operations, should_skip)

    """
    operations = []
    skip = False

    if "table" in metric_name:
        operations = [
            "r = container.exec_run("
            '"psql -U system_tests_user -d system_tests_dbname '
            '-c \\"CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY);\\")"',
            f'logger.info(f"{metric_name}: {{r.output}}")',
        ]
    elif "commit" in metric_name or "rollback" in metric_name:
        operations = [
            "r = container.exec_run("
            '"psql -U system_tests_user -d system_tests_dbname '
            '-c \\"INSERT INTO test_table DEFAULT VALUES;\\")"',
            f'logger.info(f"{metric_name}: {{r.output}}")',
        ]
    elif "connection" in metric_name:
        operations = [
            'r = container.exec_run("psql -U system_tests_user -d system_tests_dbname -c \\"SELECT 1;\\")"',
            f'logger.info(f"{metric_name}: {{r.output}}")',
        ]
    elif "replica" in metric_name or "replication" in metric_name:
        operations = [
            f"# SKIPPED: {metric_name} - requires PostgreSQL replica setup",
        ]
        skip = True
    elif "deadlock" in metric_name:
        operations = [
            f"# SKIPPED: {metric_name} - requires complex multi-transaction setup",
        ]
        skip = True
    else:
        operations = [
            'r = container.exec_run("psql -U system_tests_user -d system_tests_dbname -c \\"SELECT 1;\\")"',
            f'logger.info(f"{metric_name}: {{r.output}}")',
        ]

    return operations, skip


def generate_smoke_operations_from_metrics(
    integration_name: str,
    metrics_json_path: Path,
) -> tuple[list[str], list[str]]:
    """Generate smoke test operations by analyzing metrics JSON file.

    Args:
        integration_name: Name of the integration (e.g., "kafka", "redis")
        metrics_json_path: Path to the metrics JSON file

    Returns:
        Tuple of (all_operations, expected_metrics)

    """
    # Read metrics from JSON
    try:
        with open(metrics_json_path, "r") as f:
            metrics_data = json.load(f)
    except FileNotFoundError:
        # If metrics file doesn't exist yet, return basic operations
        return [
            f'logger.info("Add specific {integration_name} operations here")',
        ], [f"{integration_name}.metric1"]

    # Select appropriate generator
    generators = {
        "postgres": generate_postgres_operation,
        "postgresql": generate_postgres_operation,
    }

    generator = generators.get(integration_name.lower())
    if not generator:
        # Fallback for unknown integrations
        return [
            f'logger.info("Add specific {integration_name} operations for each metric")',
        ], list(metrics_data.keys())[:5]

    all_operations = []
    expected_metrics = []
    seen_operations = set()  # Deduplicate operations

    # Add header comment
    all_operations.append(f'"""Generate activity for each metric in {metrics_json_path.name}"""')

    for metric_name in metrics_data:
        operations, should_skip = generator(metric_name)

        # Deduplicate operations
        op_key = "\n".join(operations)
        if op_key in seen_operations:
            continue
        seen_operations.add(op_key)

        # Add blank line before each metric section
        if all_operations and all_operations[-1] != "":
            all_operations.append("")

        all_operations.extend(operations)

        # Only add to expected metrics if not skipped
        if not should_skip:
            expected_metrics.append(metric_name)

    # If no expected metrics, add a few common ones
    if not expected_metrics and metrics_data:
        expected_metrics = list(metrics_data.keys())[:5]

    return all_operations, expected_metrics
