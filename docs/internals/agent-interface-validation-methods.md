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

## Methods

### Data Retrieval Methods
- `get_spans(request=None)` - Get spans submitted to backend, optionally filtered by request
- `get_spans_list(request)` - Get spans for a specific request as a list
- `get_appsec_data(request)` - Get AppSec data from spans for a specific request
- `get_telemetry_data(*, flatten_message_batches=True)` - Get telemetry data sent to backend
- `get_profiling_data()` - Get profiling data from `/api/v2/profile` endpoint
- `get_metrics()` - Get metrics submitted to `/api/v2/series` endpoint
- `get_sketches()` - Get distribution sketches from `/api/beta/sketches` endpoint
- `get_stats(resource="")` - Get APM stats from `/api/v0.2/stats`, optionally filtered by resource
- `get_dsm_data()` - Get Data Streams Monitoring data from `/api/v0.1/pipeline_stats`

### Validation Methods
- `assert_trace_exists(request)` - Assert at least one trace exists for request
- `validate_appsec(request, validator)` - Validate AppSec data using custom validator function

### Header Validation Methods
- `assert_headers_presence(path_filter, request_headers=(), response_headers=(), check_condition=None)` - Validate presence of HTTP headers in agent communications
- `assert_headers_match(path_filter, request_headers=None, response_headers=None, check_condition=None)` - Validate HTTP headers match expected values

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