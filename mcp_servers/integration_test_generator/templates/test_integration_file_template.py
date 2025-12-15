"""Template for generating integration test files."""


def get_test_file_template(
    integration_title: str,
    integration_lower: str,
    integration_upper: str,
    feature: str,
    excluded_metrics_str: str,
    metrics_json_file: str,
    container_name: str,
    smoke_operations: str,
    expected_metrics_formatted: str,
) -> str:
    """Generate test file template with given parameters.

    Args:
        integration_title: Title-cased integration name (e.g., "Redis")
        integration_lower: Lowercase integration name (e.g., "redis")
        integration_upper: Uppercase integration name (e.g., "REDIS")
        feature: Feature name for decorator
        excluded_metrics_str: Formatted excluded metrics section
        metrics_json_file: Name of metrics JSON file
        container_name: Docker container name
        smoke_operations: Formatted smoke test operations
        expected_metrics_formatted: Formatted expected metrics list

    Returns:
        Complete test file content as string

    """
    return f'''import time
from pathlib import Path
from typing import TYPE_CHECKING

from utils import scenarios, interfaces, logger, features, context
from utils.otel_metrics_validator import OtelMetricsValidator, get_collector_metrics_from_scenario

if TYPE_CHECKING:
    from utils._context._scenarios.otel_collector import OtelCollectorScenario


# Load {integration_title} metrics specification
{excluded_metrics_str}
{integration_lower}_metrics = OtelMetricsValidator.load_metrics_from_file(
    metrics_file=Path(__file__).parent / "{metrics_json_file}",
    excluded_metrics=_EXCLUDED_{integration_upper}_METRICS,
)

# Initialize validator with {integration_title} metrics
_metrics_validator = OtelMetricsValidator({integration_lower}_metrics)


@scenarios.otel_collector
@scenarios.otel_collector_e2e
@features.{feature}
class Test_{integration_title}MetricsCollection:
    def test_{integration_lower}_metrics_received_by_collector(self):
        scenario: OtelCollectorScenario = context.scenario  # type: ignore[assignment]
        metrics_batch = get_collector_metrics_from_scenario(scenario)

        _, _, _validation_results, failed_validations = _metrics_validator.process_and_validate_metrics(metrics_batch)

        assert len(failed_validations) == 0, (
            f"Error: {{len(failed_validations)}} metrics failed the expected behavior!\\n"
            f"\\n\\nFailed validations:\\n" + "\\n".join(failed_validations)
        )


@scenarios.otel_collector_e2e
@features.{feature}
class Test_BackendValidity:
    def test_{integration_lower}_metrics_received_by_backend(self):
        """Test metrics were actually queried / received by the backend"""
        metrics_to_validate = list({integration_lower}_metrics.keys())
        query_tags = {{"rid": "otel-{integration_lower}-metrics", "host": "collector"}}

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
            logger.error(f"\\n❌ Failed validations for semantic mode combined: {{failed_metrics}}")

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
            logger.error(f"\\n❌ Failed validations for semantic mode native: {{failed_metrics}}")


@scenarios.otel_collector
@scenarios.otel_collector_e2e
@features.{feature}
class Test_Smoke:
    """{integration_title}-specific smoke test to generate database/service activity.
    This test validates that basic {integration_title} metrics are collected after operations.
    """

    def setup_main(self) -> None:
        """When the {integration_lower} container spins up, we need some activity."""
        scenario: OtelCollectorScenario = context.scenario  # type: ignore[assignment]
        container = scenario.{container_name}

        {smoke_operations}

    def test_main(self) -> None:
        observed_metrics: set[str] = set()

        expected_metrics = {{
            {expected_metrics_formatted}
        }}

        for data in interfaces.otel_collector.get_data("/api/v2/series"):
            logger.info(f"In request {{data['log_filename']}}")
            payload = data["request"]["content"]
            for serie in payload["series"]:
                metric = serie["metric"]
                observed_metrics.add(metric)
                logger.info(f"    {{metric}} {{serie['points']}}")

        all_metric_has_be_seen = True
        for metric in expected_metrics:
            if metric not in observed_metrics:
                logger.error(f"Metric {{metric}} hasn't been observed")
                all_metric_has_be_seen = False
            else:
                logger.info(f"Metric {{metric}} has been observed")

        assert all_metric_has_be_seen
'''
