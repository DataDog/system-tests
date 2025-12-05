#!/usr/bin/env python3
"""MCP Server for generating OTel integration metric test files.

This server provides tools to generate test files similar to test_postgres_metrics.py
but for different integrations (Redis, MySQL, Kafka, etc.).
"""

import json
from pathlib import Path
from typing import Any
import requests
import constants
from formatters import format_excluded_metrics, format_smoke_operations, format_expected_metrics
from templates.test_integration_file_template import get_test_file_template
from templates.prompt_template import get_generate_with_reference_prompt

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent, Resource
    import mcp.server.stdio
except ImportError:
    print("Error: MCP SDK not installed. Install with: pip install mcp")
    exit(1)

# Path to reference test files
SYSTEM_TESTS_ROOT = Path(__file__).parent.parent.parent
POSTGRES_TEST_PATH = SYSTEM_TESTS_ROOT / "tests/otel_postgres_metrics_e2e/test_postgres_metrics.py"
MYSQL_TEST_PATH = SYSTEM_TESTS_ROOT / "tests/otel_mysql_metrics_e2e/test_otel_mysql_metrics.py"


def generate_test_file(
    integration_name: str,
    metrics_json_file: str,
    excluded_metrics: list[str] | None = None,
    feature_name: str | None = None,
) -> str:
    """Generate a test file for the specified integration."""

    # Get integration config or use defaults
    config = constants.INTEGRATION_CONFIGS.get(
        integration_name.lower(),
        {
            "container_name": f"{integration_name.lower()}_container",
            "smoke_test_operations": [
                f'logger.info("Add specific {integration_name} operations here")',
            ],
            "expected_smoke_metrics": [
                f"{integration_name.lower()}.metric1",
                f"{integration_name.lower()}.metric2",
            ],
        },
    )

    integration_title = integration_name.title()
    integration_lower = integration_name.lower()
    integration_upper = integration_name.upper()
    feature = feature_name or f"{integration_lower}_receiver_metrics"

    excluded_metrics_str = format_excluded_metrics(integration_name, excluded_metrics)

    smoke_operations = format_smoke_operations(config["smoke_test_operations"])

    expected_metrics_formatted = format_expected_metrics(config["expected_smoke_metrics"])

    return get_test_file_template(
        integration_title=integration_title,
        integration_lower=integration_lower,
        integration_upper=integration_upper,
        feature=feature,
        excluded_metrics_str=excluded_metrics_str,
        metrics_json_file=metrics_json_file,
        container_name=config["container_name"],
        smoke_operations=smoke_operations,
        expected_metrics_formatted=expected_metrics_formatted,
    )


def generate_metrics_file(integration_name: str) -> str:
    """Get info about the latest otel-collector-contrib release.
    Metrics are defined in the metadata.yaml file which is provided in  response.
    We need to get the metrics from the metadata.yaml file.
    We can do this by parsing the yaml file and getting the metrics.
    We can then return in the following format:
    {
        "<metric_name>": {
            "data_type": "<data_type>",
            "description": "<metric_description>"
        },
    }

    """
    url = f"{constants.GH_BASE_API}/releases"

    headers = {
        "Accept": "application/vnd.github+json",
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    releases = response.json()  # list[dict]
    if not releases:
        return "No releases found for opentelemetry-collector-contrib."

    latest = releases[0]

    metaDataUrl = f"{constants.GH_BASE_API}/contents/receiver/{integration_name.lower()}receiver/metadata.yaml?ref={latest.get('tag_name')}"

    response = requests.get(metaDataUrl, headers=headers)
    if response.status_code != 200:
        return f"Failed to fetch metadata.yaml for {integration_name}."

    metadata_content = response.json().get("content")
    if not metadata_content:
        return "No content found in metadata.yaml."

    # The content is base64-encoded per GitHub API
    import base64

    try:
        decoded_yaml = base64.b64decode(metadata_content).decode("utf-8")
    except Exception as e:
        return f"Error decoding metadata.yaml content: {e}"

    # Parse YAML to get metrics info
    try:
        import yaml

        yaml_data = yaml.safe_load(decoded_yaml)
    except Exception as e:
        return f"Error parsing YAML: {e}"

    metric_template = {}
    # Try both metrics and telemetry.metrics paths
    metrics_dict = yaml_data.get("metrics", {})
    if not metrics_dict and "telemetry" in yaml_data:
        metrics_dict = yaml_data.get("telemetry", {}).get("metrics", {})
    
    for metric_name, metric_info in metrics_dict.items():
        metric_type = set(metric_info.keys()) & constants.METRIC_TYPES
        metric_template[metric_name] = {
            "data_type": metric_type.pop() if metric_type else None,
            "description": metric_info.get("description", ""),
        }

    result_json = json.dumps(metric_template, indent=2)

    metric_file_name = f"{integration_name}_metrics.json"
    metric_file_path = constants.SYSTEM_TESTS_ROOT / f"tests/otel_{integration_name}_metrics_e2e/{metric_file_name}"
    if metric_file_path.exists():
        return "There is already a metric file created. Please delete and try again"
    # Create the parent directory if it doesn't exist
    metric_file_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(metric_file_path, "x")
    f.write(result_json)
    f.close()

    return metric_template


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
                "Uses test_postgres_metrics.py as a reference template to ensure consistency. "
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


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available reference resources."""
    resources = []
    
    if POSTGRES_TEST_PATH.exists():
        resources.append(
            Resource(
                uri=f"file://{constants.POSTGRES_TEST_PATH}",
                name="PostgreSQL Metrics Test (Reference)",
                description="Reference implementation of OTel metrics test. Use this as the gold standard for structure and patterns.",
                mimeType="text/x-python"
            )
        )
    
    if MYSQL_TEST_PATH.exists():
        resources.append(
            Resource(
                uri=f"file://{MYSQL_TEST_PATH}",
                name="MySQL Metrics Test (Reference)",
                description="MySQL metrics test implementation following PostgreSQL patterns",
                mimeType="text/x-python"
            )
        )
    
    # Add OtelMetricsValidator reference
    validator_path = SYSTEM_TESTS_ROOT / "utils/otel_metrics_validator.py"
    if validator_path.exists():
        resources.append(
            Resource(
                uri=f"file://{validator_path}",
                name="OtelMetricsValidator Utility",
                description="Shared utility for validating OTel metrics. All tests should use this.",
                mimeType="text/x-python"
            )
        )
    
    
    return resources


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource file."""
    # Extract path from file:// URI
    path = uri.replace("file://", "")
    path_obj = Path(path)
    
    if not path_obj.exists():
        raise ValueError(f"Resource not found: {uri}")
    
    with open(path_obj, "r", encoding="utf-8") as f:
        return f.read()


@app.list_prompts()
async def list_prompts():
    """List available prompts."""
    from mcp.types import Prompt, PromptArgument
    
    return [
        Prompt(
            name="generate_with_reference",
            description="Generate a new integration test using PostgreSQL test as reference",
            arguments=[
                PromptArgument(
                    name="integration_name",
                    description="Name of the integration (e.g., redis, kafka, mongodb)",
                    required=True
                ),
                PromptArgument(
                    name="metrics_json_file",
                    description="Name of the metrics JSON file",
                    required=True
                ),
            ]
        )
    ]


@app.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None = None):
    """Get a specific prompt."""
    from mcp.types import PromptMessage, TextContent as PromptTextContent
    
    if name == "generate_with_reference":
        integration_name = arguments.get("integration_name", "example") if arguments else "example"
        metrics_json_file = arguments.get("metrics_json_file", "example_metrics.json") if arguments else "example_metrics.json"
        
        # Read the PostgreSQL test as reference
        postgres_test_content = ""
        if POSTGRES_TEST_PATH.exists():
            with open(POSTGRES_TEST_PATH, "r", encoding="utf-8") as f:
                postgres_test_content = f.read()
        
        prompt_text = get_generate_with_reference_prompt(
            integration_name=integration_name,
            metrics_json_file=metrics_json_file,
            postgres_test_content=postgres_test_content,
        )
        
        return PromptMessage(
            role="user",
            content=PromptTextContent(
                type="text",
                text=prompt_text
            )
        )
    
    raise ValueError(f"Unknown prompt: {name}")


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
                "import_statement": "from utils.otel_metrics_validator import OtelMetricsValidator, get_collector_metrics_from_scenario",
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

    if name == "list_supported_integrations":
        result = {
            "supported_integrations": list(constants.INTEGRATION_CONFIGS.keys()),
            "details": {
                name: {
                    "container_name": config["container_name"],
                    "expected_metrics_count": len(config["expected_smoke_metrics"]),
                }
                for name, config in constants.INTEGRATION_CONFIGS.items()
            },
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "generate_metrics_json_template":
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

    if name == "get_shared_utility_info":
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
                        "query_backend_for_metrics() - Query Datadog backend",
                    ],
                }
            },
            "helper_functions": {
                "get_collector_metrics_from_scenario": "Helper to get metrics from OtelCollectorScenario"
            },
            "benefits": [
                "No code duplication across integration tests",
                "Single source of truth for validation logic",
                "Consistent behavior across all integrations",
                "Easier maintenance - fix once, applies everywhere",
            ],
            "example_usage": """
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
""",
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

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
