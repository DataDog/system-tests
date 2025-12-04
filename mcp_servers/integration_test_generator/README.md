# Integration Test Generator MCP Server

This MCP server helps generate OTel integration metric test files similar to `test_postgres_metrics.py` but for different integrations (Redis, MySQL, Kafka, Nginx, etc.).

## Features

- **Generate complete test files** with all three test classes:
  - `Test_<Integration>MetricsCollection` - validates metrics received by collector
  - `Test_BackendValidity` - validates metrics received by backend
  - `Test_Smoke` - generates integration-specific activity and validates basic metrics

- **Uses shared utilities**:
  - All tests use the shared `utils/otel_metrics_validator.py`

- **Generates supporting files**:
  - `__init__.py`
  - Template for metrics JSON file

## Installation

### 1. Install MCP SDK

```bash
pip install mcp
```

### 2. Configure in Cursor/Claude Desktop

Add to your MCP configuration file:

**For Cursor** (`~/.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "integration-test-generator": {
      "command": "python3",
      "args": [
        "/Users/<firstname.lastname>/system-tests/mcp_servers/integration_test_generator/server.py"
      ]
    }
  }
}
```

**For Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "integration-test-generator": {
      "command": "python3",
      "args": [
        "/Users/quinna.halim/system-tests/mcp_servers/integration_test_generator/server.py"
      ]
    }
  }
}
```

### 3. Restart Cursor/Claude Desktop

## Usage

### Basic Usage

In Cursor or Claude Desktop, you can now use natural language to generate tests, i.e.:

```
Create a MySQL integration test, excluding the metrics: mysql.slow_queries, mysql.replication.delay
```

### Available Tools

#### 1. `generate_integration_test`

Generates a complete test file structure for an integration.

**Parameters:**
- `integration_name` (required): Name of the integration (e.g., "redis", "mysql")
- `metrics_json_file` (required): Name of the metrics JSON file (e.g., "redis_metrics.json")
- `excluded_metrics` (optional): List of metrics to exclude
- `feature_name` (optional): Feature name for decorator (defaults to `<integration>_receiver_metrics`)

**Example:**
```
Generate an integration test for Redis with metrics file redis_metrics.json and exclude redis.cluster.slots
```

#### 2. `list_supported_integrations`

Lists all integrations with pre-configured smoke tests.

**Example:**
```
What integrations are supported?
```

#### 3. `generate_metrics_json_template`

Creates a template metrics JSON file structure.

**Parameters:**
- `integration_name` (required): Name of the integration
- `sample_metrics` (required): List of sample metric names

**Example:**
```
Generate a metrics JSON template for Redis with metrics: redis.commands.processed, redis.net.input, redis.keys.expired
```

## Workflow

### Step 1: Generate the Test Files

```
Ex: Generate a MySQL integration test with metrics file mysql_metrics.json
```

The MCP server will provide:
1. `test_mysql_metrics.py` - The main test file
2. `__init__.py` - Package init file
3. Directory structure instructions

### Step 2: Create the Directory

```bash
mkdir -p tests/otel_redis_metrics_e2e
```

### Step 3: Create the Metrics JSON

Create `tests/otel_<integration>_metrics_e2e/<integration>_metrics.json`:

```json
{
  "postgresql.backends": {
    "data_type": "Sum",
    "description": "The number of backends."
  },
  "postgresql.bgwriter.buffers.allocated": {
    "data_type": "Sum",
    "description": "Number of buffers allocated."
  },
}
```


### Step 4: Customize the Smoke Test

Review and update the smoke test operations in `test_<integration>_metrics.py` if needed:

```python
def setup_main(self) -> None:
    """When the container spins up, we need some activity."""
    scenario: OtelCollectorScenario = context.scenario
    container = scenario.redis_container

    # Customize these operations for your integration
    r = container.exec_run("redis-cli SET test_key test_value")
    logger.info(r.output)
    # ... more operations
```

### Step 5: Add Feature to utils/_features.py

If the feature doesn't exist, add it:

```python
@staticmethod
def postgres_receiver_metrics(test_object):
    """OpenTelemetry semantic conventions for Postgres receiver metrics

    https://feature-parity.us1.prod.dog/#/?feature=498
    """
    return _mark_test_object(test_object, feature_id=498, owner=_Owner.idm)
```

### Step 6: Format and Test

```bash
./format.sh
./run.sh otel_collector  # or appropriate scenario
```


## Example Outputs

### For MySQL

The generator will create:
- MySQL-specific database operations (CREATE DATABASE, CREATE TABLE, INSERT, SELECT)
- Expected metrics for MySQL operations
- Proper container reference (`mysql_container`)

## Troubleshooting

### MCP Server Not Showing Up

1. Check the configuration file path is correct
2. Ensure the Python path in configuration matches your system
3. Restart Cursor/Claude Desktop after configuration changes
4. Check logs:
   - Cursor: Developer Tools → Console
   - Claude Desktop: Console logs

### Import Errors

Ensure MCP SDK is installed:
```bash
pip install mcp
```

### Permission Issues

Make the server executable:
```bash
chmod +x /Users/quinna.halim/system-tests/mcp_servers/integration_test_generator/server.py
```

## Next Steps

1. **Extend INTEGRATION_CONFIGS**: Add more pre-configured integrations
2. **Custom Templates**: Create specialized templates for different test patterns
3. **Metrics Discovery**: Add tools to discover metrics from OTel Collector configuration
4. **Validation**: Add tools to validate generated tests against existing patterns

## References

- [MCP Documentation](https://modelcontextprotocol.io/)
- [System Tests Documentation](../../docs/)
- [OTel Metrics Testing Guide](../../docs/scenarios/otel_collector.md)

