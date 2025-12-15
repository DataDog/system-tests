from pathlib import Path

METRIC_TYPES = {"sum", "gauge"}
GH_BASE_API = "https://api.github.com/repos/open-telemetry/opentelemetry-collector-contrib"

# Path to reference test files
SYSTEM_TESTS_ROOT = Path(__file__).parent.parent.parent
POSTGRES_TEST_PATH = SYSTEM_TESTS_ROOT / "tests/otel_postgres_metrics_e2e/test_postgres_metrics.py"


# Integration-specific configurations
# This is empty by default - the MCP server generates tests dynamically
# based on the metrics JSON file and the Postgres reference implementation
INTEGRATION_CONFIGS = {}
