# External Environment Header Test

This test verifies that the `datadog-external-env` HTTP header is correctly set in requests to the test agent with the value from the `DD_EXTERNAL_ENV` environment variable.

## Test Description

The test file `test_external_env_header.py` contains two test methods:

### `test_datadog_external_env_header_set`

This test verifies that when the `DD_EXTERNAL_ENV` environment variable is set, the `datadog-external-env` header is present in requests to the agent and contains the correct value.

**Parameters:**
- `library_env`: A dictionary containing the `DD_EXTERNAL_ENV` environment variable with different test values:
  - `"test-env-value"`: Simple single value
  - `"prod-env,staging-env"`: Multiple comma-separated values
  - `"it-false,cn-weblog,pu-75a2b6d5-3949-4afb-ad0d-92ff0674e759"`: Complex value matching the format used in the default scenario

### `test_datadog_external_env_header_not_set_when_env_var_missing`

This test verifies that when the `DD_EXTERNAL_ENV` environment variable is not set, the `datadog-external-env` header is not present in requests to the agent.

## Implementation Details

The test:
1. Creates a span using `test_library.dd_start_span("test_span")` to generate a trace
2. Waits for the trace to be sent to the agent using `test_agent.wait_for_num_traces(1)`
3. Retrieves all requests made to the agent using `test_agent.requests()`
4. Filters for requests to the `/traces` endpoint
5. Verifies the presence and value of the `datadog-external-env` header

## Missing Feature Decorators

The test includes `@missing_feature` decorators for:
- PHP: "not implemented yet"
- Ruby: "not implemented yet" 
- Go versions < 1.73.0-dev: "Implemented in v1.72.0"

These decorators ensure the test is skipped for languages/versions that don't yet support the `datadog-external-env` header functionality.

## Related Documentation

This test complements the existing end-to-end test in `tests/test_data_integrity.py` which verifies the format of the `datadog-external-env` header when present. The parametric test specifically focuses on verifying that the header value matches the environment variable value. 