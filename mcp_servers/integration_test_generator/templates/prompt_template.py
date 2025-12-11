"""Template for generating prompts."""


def get_generate_with_reference_prompt(
    integration_name: str,
    metrics_json_file: str,
    postgres_test_content: str,
) -> str:
    """Generate prompt for creating integration test with PostgreSQL reference.
    
    Args:
        integration_name: Name of the integration (e.g., "redis")
        metrics_json_file: Name of the metrics JSON file
        postgres_test_content: Content of the PostgreSQL reference test
    
    Returns:
        Complete prompt text as string
    """
    return f"""You are generating an OTel integration metrics test for {integration_name}.

CRITICAL: Use the PostgreSQL test as your REFERENCE TEMPLATE. Follow its structure exactly.

## PostgreSQL Test Reference (GOLD STANDARD):

```python
{postgres_test_content}
```

## Requirements for {integration_name} test:

1. **Structure**: Follow PostgreSQL test structure EXACTLY:
   - Three separate test classes (not one big class)
   - Test_{{Integration}}MetricsCollection
   - Test_BackendValidity  
   - Test_Smoke

2. **Use OtelMetricsValidator**: Import and use the shared validator
   ```python
   from utils.otel_metrics_validator import OtelMetricsValidator, get_collector_metrics_from_scenario
   ```

3. **Correct Decorators**: 
   - Use scenario-specific decorator: @scenarios.otel_{integration_name}_metrics_e2e

4. **Real Metrics**: Use actual metrics from {integration_name} receiver
   - Do NOT invent fake metrics

5. **Correct Credentials**: Use system_tests credentials
   - User: system_tests_user
   - Password: system_tests_password
   - Database: system_tests_dbname

6. **Retry Logic**: Backend queries MUST have:
   - retries=3
   - initial_delay_s=0.5
   - Both "combined" and "native" semantic modes

7. **Smoke Test**: Generate real activity on the container
   - Access via: scenario.{integration_name}_container
   - Look at each of the metrics in the generated metrics file. For each metric, run a command to generate activity on the container. 
   - Skip metrics that involve replica DBs, deadlocks, or that require a second instance of the integration that's running.
   - If a metric is skipped, leave a comment in the test file explaining why it was skipped.
   - Look at the postgres_metrics.json file as an example.
   - Example:
     - For the metric "redis.commands.processed", run the command "redis-cli INCR counter"
     - For the metric "redis.keys.expired", run the command "redis-cli FLUSHALL"
     - For the metric "redis.net.input", run the command "redis-cli GET test_key"
     - For the metric "redis.net.output", run the command "redis-cli SET test_key test_value"
   - If unable to find the command, skip the metric and leave a comment in the test file explaining why it was skipped.
   - Run actual commands (CREATE, INSERT, SELECT for databases)

8. **Test Pattern**:
   ```python
   def test_main(self) -> None:
       observed_metrics: set[str] = set()
       expected_metrics = {{...}}
       
       for data in interfaces.otel_collector.get_data("/api/v2/series"):
           # ... collect metrics
       
       missing_metrics = expected_metrics - observed_metrics
       assert not missing_metrics, f"Missing metrics: {{missing_metrics}}"
   ```

Generate the complete test file for {integration_name} with metrics file {metrics_json_file}.
"""

