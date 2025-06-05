# Agent Interface Validation Methods

This document provides a comprehensive overview of all validation methods available in the `AgentInterfaceValidator` class. The agent interface validates messages intercepted between the Datadog Agent and the Datadog Backend.

## Overview

The `AgentInterfaceValidator` is instantiated as a singleton in `utils/interfaces/__init__.py` and can be accessed as `interfaces.agent` in your test cases. It intercepts and validates JSON messages stored in the `logs_<scenario_name>/interfaces/agent` folder.

## Usage Pattern

```python
from utils import interfaces, weblog
from utils import scenarios

@scenarios.scenario
class MyTestClass:
    def setup_my_test(self):
        # Generate traces by making requests
        self.r = weblog.get("/endpoint")

    def test_my_validation(self):
        # Use validation methods to verify intercepted data
        interfaces.agent.assert_trace_exists(self.r)

        # Validate custom span data
        def span_validator(span):
            return span.get("service") == "my-service"

        spans = list(interfaces.agent.get_spans(self.r))
        assert any(span_validator(span) for _, span in spans)
```

## Data Retrieval Methods

These methods help you retrieve intercepted data for analysis:

### `get_spans(request=None)`
- **Purpose**: Get spans that the agent submits to the backend
- **Parameters**:
  - `request`: `HttpResponse | None` - Filter spans by request ID
- **Returns**: Iterator of `(data, span)` tuples
- **Usage**: Fetch all spans or those related to a specific request
- **Note**: When request is provided, only spans sampled during that request's execution are returned

### `get_spans_list(request)`
- **Purpose**: Get a list of spans for a specific request
- **Parameters**:
  - `request`: `HttpResponse` - Required request object
- **Returns**: List of span dictionaries
- **Usage**: Convenience method to get spans as a list instead of iterator

### `get_appsec_data(request)`
- **Purpose**: Get AppSec data from spans submitted to the backend
- **Parameters**:
  - `request`: `HttpResponse` - Request that generated AppSec events
- **Returns**: Iterator of `(data, payload, chunk, span, appsec_data)` tuples
- **Usage**: Extract AppSec events from agent traces

### `get_telemetry_data(*, flatten_message_batches=True)`
- **Purpose**: Get telemetry data sent from agent to backend
- **Parameters**:
  - `flatten_message_batches`: `bool` - Whether to flatten batched telemetry messages
- **Returns**: Iterator of telemetry data
- **Usage**: Access telemetry information sent through the agent

### `get_profiling_data()`
- **Purpose**: Get profiling data sent from agent to backend
- **Returns**: Iterator of profiling data from `/api/v2/profile` endpoint
- **Usage**: Validate profiling data flow through the agent

### `get_metrics()`
- **Purpose**: Get metrics that the agent submits to the backend
- **Returns**: Iterator of `(data, point)` tuples
- **Usage**: Validate metrics collection and submission
- **Endpoint**: Monitors `/api/v2/series` endpoint

### `get_sketches()`
- **Purpose**: Get distribution sketches that the agent submits to the backend
- **Returns**: Iterator of `(data, point)` tuples
- **Usage**: Validate distribution metrics (histograms, timing data)
- **Endpoint**: Monitors `/api/beta/sketches` endpoint

### `get_stats(resource="")`
- **Purpose**: Get APM stats that the agent submits to the backend
- **Parameters**:
  - `resource`: `str` - Optional resource filter (empty string means all resources)
- **Returns**: Iterator of grouped statistics
- **Usage**: Validate APM statistics aggregation and submission
- **Endpoint**: Monitors `/api/v0.2/stats` endpoint

### `get_dsm_data()`
- **Purpose**: Get Data Streams Monitoring (DSM) data
- **Returns**: Iterator of DSM data from `/api/v0.1/pipeline_stats` endpoint
- **Usage**: Validate data pipeline statistics

## Validation Methods

### `assert_trace_exists(request)`
- **Purpose**: Assert that at least one trace exists for a specific request
- **Parameters**:
  - `request`: `HttpResponse` - Request that should have generated traces
- **Raises**: `ValueError` if no traces are found for the request
- **Usage**: Ensure basic trace collection is working

### `validate_appsec(request, validator)`
- **Purpose**: Validate AppSec data using a custom validator function
- **Parameters**:
  - `request`: `HttpResponse` - Request that generated AppSec events
  - `validator`: `Callable` - Function that takes `(data, payload, chunk, span, appsec_data)` and returns boolean
- **Raises**: `ValueError` if no data validates the test
- **Usage**: Custom validation of AppSec events at the agent level

### `validate_telemetry(validator, *, success_by_default=False)`
- **Purpose**: Validate telemetry data using a custom validator function
- **Parameters**:
  - `validator`: `Callable` - Function to validate telemetry data
  - `success_by_default`: `bool` - Whether to succeed if no telemetry found
- **Note**: Automatically skips APM onboarding events
- **Usage**: Custom validation of telemetry messages

### `validate_profiling(validator, *, success_by_default=False)`
- **Purpose**: Validate profiling data using a custom validator function
- **Parameters**:
  - `validator`: `Callable` - Function to validate profiling data
  - `success_by_default`: `bool` - Whether to succeed if no profiling data found
- **Usage**: Custom validation of profiling submissions

### `add_traces_validation(validator, *, success_by_default=False)`
- **Purpose**: Add a trace validation that applies to all trace data
- **Parameters**:
  - `validator`: `Callable` - Validation function for trace data
  - `success_by_default`: `bool` - Default success behavior
- **Usage**: Apply validation across all trace submissions

## Header Validation Methods

### `assert_headers_presence(path_filter, request_headers=(), response_headers=(), check_condition=None)`
- **Purpose**: Validate the presence of HTTP headers in agent communications
- **Parameters**:
  - `path_filter`: `Iterable[str] | str | None` - Path filters to check
  - `request_headers`: `Iterable[str]` - Headers to validate in requests
  - `response_headers`: `Iterable[str]` - Headers to validate in responses
  - `check_condition`: `Callable | None` - Additional condition function
- **Usage**: Ensure required headers are present in agent communications

### `assert_headers_match(path_filter, request_headers=None, response_headers=None, check_condition=None)`
- **Purpose**: Validate that HTTP headers match expected values
- **Parameters**:
  - `path_filter`: `list[str] | str | None` - Path filters to check
  - `request_headers`: `dict | None` - Headers and expected values for requests
  - `response_headers`: `dict | None` - Headers and expected values for responses
  - `check_condition`: `Callable | None` - Additional condition function
- **Usage**: Ensure headers have correct values in agent communications

## Key Differences from Library Interface

The agent interface differs from the library interface in several important ways:

1. **Data Source**: Validates data **after** it has been processed by the agent, not raw tracer output
2. **Endpoints**: Monitors backend API endpoints (`/api/v0.2/traces`, `/api/v2/series`, etc.)
3. **Data Structure**: Works with agent-formatted payloads including `tracerPayloads`, `chunks`, and aggregated data
4. **Scope**: Focuses on agent-to-backend communication rather than tracer-to-agent

## Best Practices

1. **Use request filtering**: Always filter by specific requests when possible to avoid interference from other tests

2. **Understand data flow**: Agent interface data represents what reaches the backend, which may be sampled, aggregated, or modified by the agent

3. **Combine with library validation**: Use both library and agent interfaces together to validate the complete data pipeline

4. **Check data transformation**: Verify that data transformations performed by the agent are correct

5. **Validate aggregations**: Use stats and metrics methods to ensure proper aggregation by the agent

## Common Patterns

### Basic Trace Validation
```python
def test_agent_trace_forwarding(self):
    r = weblog.get("/")
    interfaces.agent.assert_trace_exists(r)

    # Verify spans reach the backend with correct structure
    spans = list(interfaces.agent.get_spans(r))
    assert len(spans) > 0

    for _, span in spans:
        assert "trace_id" in span
        assert "span_id" in span
```

### AppSec Event Validation
```python
def test_appsec_agent_forwarding(self):
    r = weblog.get("/", headers={"X-Attack": "' OR 1=1--"})

    def appsec_validator(data, payload, chunk, span, appsec_data):
        return "triggers" in appsec_data

    interfaces.agent.validate_appsec(r, appsec_validator)
```

### Metrics Validation
```python
def test_agent_metrics_collection(self):
    r = weblog.get("/")

    # Check that metrics are properly collected and forwarded
    metrics = list(interfaces.agent.get_metrics())
    assert len(metrics) > 0

    for _, metric in metrics:
        assert "metric" in metric
        assert "points" in metric
```

### Stats Validation
```python
def test_agent_stats_aggregation(self):
    r = weblog.get("/")

    # Verify stats are aggregated by resource
    stats = list(interfaces.agent.get_stats(resource="/"))
    assert len(stats) > 0

    for stat in stats:
        assert stat["Resource"] == "/"
        assert "Hits" in stat
        assert "Duration" in stat
```

### Telemetry Validation
```python
def test_agent_telemetry_forwarding(self):
    def telemetry_validator(data):
        content = data["request"]["content"]
        return content.get("request_type") == "generate-metrics"

    interfaces.agent.validate_telemetry(telemetry_validator)
```

### Custom Span Validation
```python
def test_custom_span_processing(self):
    r = weblog.get("/")

    def span_validator(data):
        content = data["request"]["content"]
        if "tracerPayloads" not in content:
            return False

        for payload in content["tracerPayloads"]:
            for chunk in payload["chunks"]:
                for span in chunk["spans"]:
                    if span.get("service") == "my-service":
                        return True
        return False

    interfaces.agent.add_traces_validation(span_validator)
```

## Data Flow Understanding

The agent interface sits in the middle of the data pipeline:

```
[Tracer] → [Agent] → [Backend]
           ↑
    Agent Interface
    (validates here)
```

This means:
- Data has been processed/transformed by the agent
- Sampling decisions have been applied
- Stats aggregation has occurred
- Rate limiting may have been applied

## Common Use Cases

1. **End-to-End Validation**: Ensure data flows completely through the system
2. **Agent Processing**: Verify agent correctly processes and forwards data
3. **Sampling Verification**: Check that sampling decisions are properly applied
4. **Aggregation Testing**: Validate stats and metrics aggregation
5. **Performance Monitoring**: Ensure profiling and metrics collection works
6. **Security Integration**: Verify AppSec events are properly forwarded

## Related Documentation

- [Agent Interface Core Implementation](../../utils/interfaces/_agent.py)
- [Interface Initialization](../../utils/interfaces/__init__.py)
- [Library Interface Validation Methods](./library-interface-validation-methods.md)
- [End-to-End Testing Guide](../execute/README.md)
- [Adding New Tests](../edit/add-new-test.md)