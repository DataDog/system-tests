#!/usr/bin/env python3
"""MCP Server for generating OTel integration metric test files.

This server provides tools to generate test files similar to test_postgres_metrics.py
but for different integrations (Redis, MySQL, Kafka, etc.).
"""

import json
from pathlib import Path
from typing import Any

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    import mcp.server.stdio
except ImportError:
    print("Error: MCP SDK not installed. Install with: pip install mcp")
    exit(1)


# Integration-specific configurations
INTEGRATION_CONFIGS = {
    "redis": {
        "container_name": "redis_container",
        "smoke_test_operations": [
            'r = container.exec_run("redis-cli SET test_key test_value")',
            'logger.info(r.output)',
            'r = container.exec_run("redis-cli GET test_key")',
            'logger.info(r.output)',
            'r = container.exec_run("redis-cli INCR counter")',
            'logger.info(r.output)',
        ],
        "expected_smoke_metrics": [
            "redis.commands.processed",
            "redis.keys.expired",
            "redis.net.input",
            "redis.net.output",
        ],
    },
    "mysql": {
        "container_name": "mysql_container",
        "smoke_test_operations": [
            'r = container.exec_run("mysql -u root -ppassword -e \'CREATE DATABASE IF NOT EXISTS test_db;\'")',
            'r = container.exec_run("mysql -u root -ppassword test_db -e \'CREATE TABLE IF NOT EXISTS test_table (id INT PRIMARY KEY);\'")',
            'r = container.exec_run("mysql -u root -ppassword test_db -e \'INSERT INTO test_table VALUES (1);\'")',
            'logger.info(r.output)',
            'r = container.exec_run("mysql -u root -ppassword test_db -e \'SELECT * FROM test_table;\'")',
            'logger.info(r.output)',
        ],
        "expected_smoke_metrics": [
            "mysql.operations",
            "mysql.client.network.io",
            "mysql.commands",
        ],
    },
    "nginx": {
        "container_name": "nginx_container",
        "smoke_test_operations": [
            'r = container.exec_run("curl -s http://localhost/status")',
            'logger.info(r.output)',
        ],
        "expected_smoke_metrics": [
            "nginx.requests",
            "nginx.connections_accepted",
            "nginx.connections_handled",
        ],
    },
    "kafka": {
        "container_name": "kafka_container",
        "smoke_test_operations": [
            'r = container.exec_run("kafka-topics --create --topic test-topic --bootstrap-server localhost:9092")',
            'logger.info(r.output)',
            'r = container.exec_run("kafka-console-producer --topic test-topic --bootstrap-server localhost:9092", stdin="test message")',
        ],
        "expected_smoke_metrics": [
            "kafka.messages",
            "kafka.brokers",
        ],
    },
}


def generate_test_file(
    integration_name: str,
    metrics_json_file: str,
    excluded_metrics: list[str] | None = None,
    feature_name: str | None = None,
) -> str:
    """Generate a test file for the specified integration."""
    
    # Get integration config or use defaults
    config = INTEGRATION_CONFIGS.get(integration_name.lower(), {
        "container_name": f"{integration_name.lower()}_container",
        "smoke_test_operations": [
            f'logger.info("Add specific {integration_name} operations here")',
        ],
        "expected_smoke_metrics": [
            f"{integration_name.lower()}.metric1",
            f"{integration_name.lower()}.metric2",
        ],
    })
    
    integration_title = integration_name.title()
    integration_lower = integration_name.lower()
    feature = feature_name or f"{integration_lower}_receiver_metrics"
    
    # Format excluded metrics
    excluded_metrics_str = ""
    if excluded_metrics:
        excluded_metrics_formatted = ",\n    ".join([f'"{m}"' for m in excluded_metrics])
        excluded_metrics_str = f"""
# Exclude metrics that require specific setup or sustained activity
_EXCLUDED_{integration_name.upper()}_METRICS = {{
    {excluded_metrics_formatted}
}}
"""
    else:
        excluded_metrics_str = f"_EXCLUDED_{integration_name.upper()}_METRICS: set[str] = set()"
    
    # Format smoke test operations
    smoke_operations = "\n        ".join(config["smoke_test_operations"])
    
    # Format expected smoke metrics
    expected_metrics_formatted = ",\n            ".join([f'"{m}"' for m in config["expected_smoke_metrics"]])
    
    template = f'''import time
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
    excluded_metrics=_EXCLUDED_{integration_name.upper()}_METRICS,
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
        container = scenario.{config["container_name"]}

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
    
    return template


def generate_init_file() -> str:
    """Generate __init__.py file."""
    return ""


# Initialize MCP server
app = Server("integration-test-generator")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="generate_integration_test",
            description=(
                "Generate a complete test file for an OTel integration (like Redis, MySQL, Kafka, etc.). "
                "Provides the test file content, utils.py content, and __init__.py content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "integration_name": {
                        "type": "string",
                        "description": "Name of the integration (e.g., 'redis', 'mysql', 'kafka', 'nginx')",
                    },
                    "metrics_json_file": {
                        "type": "string",
                        "description": "Name of the metrics JSON file (e.g., 'redis_metrics.json')",
                    },
                    "excluded_metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of metric names to exclude (optional)",
                    },
                    "feature_name": {
                        "type": "string",
                        "description": "Feature name for the @features decorator (optional, defaults to <integration>_receiver_metrics)",
                    },
                },
                "required": ["integration_name", "metrics_json_file"],
            },
        ),
        Tool(
            name="list_supported_integrations",
            description="List integrations with pre-configured smoke tests and expected metrics",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="generate_metrics_json_template",
            description="Generate a template metrics JSON file structure",
            inputSchema={
                "type": "object",
                "properties": {
                    "integration_name": {
                        "type": "string",
                        "description": "Name of the integration",
                    },
                    "sample_metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of sample metric names",
                    },
                },
                "required": ["integration_name", "sample_metrics"],
            },
        ),
        Tool(
            name="get_shared_utility_info",
            description="Get information about the shared OtelMetricsValidator utility",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "generate_integration_test":
        integration_name = arguments["integration_name"]
        metrics_json_file = arguments["metrics_json_file"]
        excluded_metrics = arguments.get("excluded_metrics")
        feature_name = arguments.get("feature_name")
        
        test_content = generate_test_file(
            integration_name=integration_name,
            metrics_json_file=metrics_json_file,
            excluded_metrics=excluded_metrics,
            feature_name=feature_name,
        )
        
        init_content = generate_init_file()
        
        result = {
            "test_file": {
                "filename": f"test_{integration_name.lower()}_metrics.py",
                "content": test_content,
            },
            "init_file": {
                "filename": "__init__.py",
                "content": init_content,
            },
            "shared_utility": {
                "note": "Uses shared OtelMetricsValidator from utils/otel_metrics_validator.py",
                "location": "utils/otel_metrics_validator.py",
                "import_statement": "from utils.otel_metrics_validator import OtelMetricsValidator, get_collector_metrics_from_scenario"
            },
            "directory_structure": f"""
Create the following directory structure:

tests/otel_{integration_name.lower()}_metrics_e2e/
├── __init__.py
├── test_{integration_name.lower()}_metrics.py
└── {metrics_json_file}

NOTE: No utils.py needed! The test file imports from shared utils.otel_metrics_validator

Next steps:
1. Create the metrics JSON file with your integration's metric specifications
2. Update the smoke test operations in test_{integration_name.lower()}_metrics.py if needed
3. Update expected_smoke_metrics with actual metrics from your integration
4. Add the feature to utils/_features.py if it doesn't exist
5. Run './format.sh' to ensure code formatting

The shared OtelMetricsValidator is already available at:
    utils/otel_metrics_validator.py
""",
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "list_supported_integrations":
        result = {
            "supported_integrations": list(INTEGRATION_CONFIGS.keys()),
            "details": {
                name: {
                    "container_name": config["container_name"],
                    "expected_metrics_count": len(config["expected_smoke_metrics"]),
                }
                for name, config in INTEGRATION_CONFIGS.items()
            },
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "generate_metrics_json_template":
        integration_name = arguments["integration_name"]
        sample_metrics = arguments["sample_metrics"]
        
        metrics_template = {}
        for metric_name in sample_metrics:
            metrics_template[metric_name] = {
                "data_type": "Sum",  # or "Gauge"
                "description": f"Description for {metric_name}",
            }
        
        result = {
            "filename": f"{integration_name.lower()}_metrics.json",
            "content": metrics_template,
            "note": "Update data_type to 'Sum' or 'Gauge' and provide accurate descriptions",
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "get_shared_utility_info":
        result = {
            "shared_utility": {
                "location": "utils/otel_metrics_validator.py",
                "description": "Reusable metrics validation class for all OTel integration tests",
                "import_statement": "from utils.otel_metrics_validator import OtelMetricsValidator, get_collector_metrics_from_scenario",
            },
            "classes": {
                "OtelMetricsValidator": {
                    "description": "Main class for validating OTel integration metrics",
                    "methods": [
                        "load_metrics_from_file() - Load metrics from JSON",
                        "get_collector_metrics() - Get metrics from collector logs",
                        "process_and_validate_metrics() - Validate against spec",
                        "query_backend_for_metrics() - Query Datadog backend"
                    ]
                }
            },
            "helper_functions": {
                "get_collector_metrics_from_scenario": "Helper to get metrics from OtelCollectorScenario"
            },
            "benefits": [
                "No code duplication across integration tests",
                "Single source of truth for validation logic",
                "Consistent behavior across all integrations",
                "Easier maintenance - fix once, applies everywhere"
            ],
            "example_usage": '''
# Load and validate metrics
from pathlib import Path
from utils.otel_metrics_validator import OtelMetricsValidator, get_collector_metrics_from_scenario

# Load metrics from JSON
metrics = OtelMetricsValidator.load_metrics_from_file(
    metrics_file=Path(__file__).parent / "redis_metrics.json",
    excluded_metrics={"redis.cluster.slots"}
)

# Initialize validator
validator = OtelMetricsValidator(metrics)

# Get metrics from scenario
scenario = context.scenario
metrics_batch = get_collector_metrics_from_scenario(scenario)

# Validate
_, _, results, failures = validator.process_and_validate_metrics(metrics_batch)
'''
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Main entry point for the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

