# Library Interface Validation Methods

This document provides a comprehensive overview of all validation methods available in the `LibraryInterfaceValidator` class. The library interface validates messages intercepted between instrumented applications (using Datadog tracers) and the Datadog Agent.

## Overview

The `LibraryInterfaceValidator` is instantiated as a singleton in `utils/interfaces/__init__.py` and can be accessed as `interfaces.library` in your test cases. It intercepts and validates JSON messages stored in the `logs_<scenario_name>/interfaces/library` folder.

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
        interfaces.library.assert_trace_exists(self.r)
        interfaces.library.add_span_tag_validation(
            request=self.r,
            tags={"http.status_code": "200"}
        )
```

## Data Retrieval Methods

These methods help you retrieve intercepted data for analysis:

### `get_traces(request=None)`
- **Purpose**: Get all traces, optionally filtered by a specific request
- **Parameters**:
  - `request`: `HttpResponse | GrpcResponse | None` - Filter traces by request ID
- **Returns**: Iterator of `(data, trace)` tuples
- **Usage**: Iterate over all traces or those related to a specific request

### `get_spans(request=None, *, full_trace=False)`
- **Purpose**: Iterate over all spans with flexible filtering options
- **Parameters**:
  - `request`: `HttpResponse | None` - Filter by request
  - `full_trace`: `bool` - If True, returns all spans from traces triggered by the request
- **Returns**: Iterator of `(data, trace, span)` tuples

### `get_root_spans(request=None)`
- **Purpose**: Get only root spans (spans with no parent)
- **Parameters**:
  - `request`: `HttpResponse | None` - Filter by request
- **Returns**: Iterator of `(data, span)` tuples

### `get_root_span(request)`
- **Purpose**: Get exactly one root span for a request (fails if 0 or >1 found)
- **Parameters**:
  - `request`: `HttpResponse` - Required request object
- **Returns**: Single span dictionary
- **Note**: Asserts exactly one root span exists

### `get_appsec_events(request=None, *, full_trace=False)`
- **Purpose**: Get AppSec events from trace spans
- **Parameters**:
  - `request`: `HttpResponse | None` - Filter by request
  - `full_trace`: `bool` - Include all spans from the trace
- **Returns**: Iterator of `(data, trace, span, appsec_data)` tuples

### `get_legacy_appsec_events(request=None)`
- **Purpose**: Get legacy AppSec events from dedicated endpoints
- **Parameters**:
  - `request`: `HttpResponse | None` - Filter by request
- **Returns**: Iterator of `(data, event)` tuples

### `get_telemetry_data(*, flatten_message_batches=True)`
- **Purpose**: Get telemetry data from the agent
- **Parameters**:
  - `flatten_message_batches`: `bool` - Whether to flatten batched messages
- **Returns**: Iterator of telemetry data

### `get_telemetry_metric_series(namespace, metric)`
- **Purpose**: Get specific telemetry metric series
- **Parameters**:
  - `namespace`: `str` - Metric namespace
  - `metric`: `str` - Metric name
- **Returns**: List of relevant metric series

### `get_profiling_data()`
- **Purpose**: Get profiling data
- **Returns**: Iterator of profiling data from `/profiling/v1/input` endpoint

## Trace & Span Validation Methods

### `validate_traces(request, validator, *, success_by_default=False)`
- **Purpose**: Validate traces using a custom validator function
- **Parameters**:
  - `request`: `HttpResponse` - Request to filter traces
  - `validator`: `Callable` - Function that takes a trace and returns boolean
  - `success_by_default`: `bool` - Whether to succeed if no traces found

### `validate_spans(request=None, *, validator, success_by_default=False, full_trace=False)`
- **Purpose**: Validate spans using a custom validator function
- **Parameters**:
  - `request`: `HttpResponse | None` - Optional request filter
  - `validator`: `Callable` - Function that takes a span and returns boolean
  - `success_by_default`: `bool` - Whether to succeed if no spans found
  - `full_trace`: `bool` - Include all spans from matching traces

### `add_traces_validation(validator, *, success_by_default=False)`
- **Purpose**: Add a trace validation that applies to all traces
- **Parameters**:
  - `validator`: `Callable` - Validation function
  - `success_by_default`: `bool` - Default success behavior

### `add_span_tag_validation(request=None, tags=None, *, value_as_regular_expression=False, full_trace=False)`
- **Purpose**: Validate specific span tags
- **Parameters**:
  - `request`: `HttpResponse | None` - Optional request filter
  - `tags`: `dict | None` - Tags to validate (key-value pairs)
  - `value_as_regular_expression`: `bool` - Treat tag values as regex patterns
  - `full_trace`: `bool` - Include all spans from matching traces

### `assert_trace_exists(request, span_type=None)`
- **Purpose**: Assert that a trace exists for a specific request
- **Parameters**:
  - `request`: `HttpResponse` - Request that should have generated a trace
  - `span_type`: `str | None` - Optional span type filter

### `assert_trace_id_uniqueness()`
- **Purpose**: Ensure all trace IDs are unique across all traces
- **Raises**: `ValueError` if duplicate trace IDs are found

### `assert_receive_request_root_trace()`
- **Purpose**: Assert that at least one web request root trace was received
- **Raises**: `ValueError` if no web root spans found

## AppSec Validation Methods

### `validate_appsec(request=None, validator=None, *, success_by_default=False, legacy_validator=None, full_trace=False)`
- **Purpose**: General AppSec event validation
- **Parameters**:
  - `request`: `HttpResponse | None` - Optional request filter
  - `validator`: `Callable | None` - Function to validate modern AppSec events
  - `success_by_default`: `bool` - Default success behavior
  - `legacy_validator`: `Callable | None` - Function to validate legacy AppSec events
  - `full_trace`: `bool` - Include all spans from matching traces

### `assert_waf_attack(request, rule=None, pattern=None, value=None, address=None, patterns=None, key_path=None, *, full_trace=False, span_validator=None)`
- **Purpose**: Assert that the WAF detected an attack
- **Parameters**:
  - `request`: `HttpResponse | None` - Request that triggered the attack
  - `rule`: `str | type | None` - Expected rule ID
  - `pattern`: `str | None` - Expected pattern
  - `value`: `str | None` - Expected attack value
  - `address`: `str | None` - Expected address
  - `patterns`: `list[str] | None` - List of expected patterns
  - `key_path`: `str | list[str] | None` - Expected key path
  - `full_trace`: `bool` - Look at entire trace
  - `span_validator`: `Callable | None` - Additional span validation

### `assert_rasp_attack(request, rule, parameters=None)`
- **Purpose**: Assert that RASP detected an attack
- **Parameters**:
  - `request`: `HttpResponse` - Request that triggered the attack
  - `rule`: `str` - Expected RASP rule ID
  - `parameters`: `dict | None` - Expected attack parameters

### `assert_no_appsec_event(request)`
- **Purpose**: Assert that no AppSec events were generated for a request
- **Parameters**:
  - `request`: `HttpResponse` - Request that should not trigger AppSec
- **Raises**: `ValueError` if any AppSec events are found

### `add_appsec_reported_header(request, header_name)`
- **Purpose**: Validate that a specific header was reported in AppSec events
- **Parameters**:
  - `request`: `HttpResponse` - Request containing the header
  - `header_name`: `str` - Name of the header to validate

### `assert_iast_implemented()`
- **Purpose**: Assert that IAST (Interactive Application Security Testing) is implemented
- **Raises**: `ValueError` if `_dd.iast.enabled` is not found in span metadata

## Telemetry Validation Methods

### `validate_telemetry(validator, *, success_by_default=False)`
- **Purpose**: Validate telemetry data using a custom validator
- **Parameters**:
  - `validator`: `Callable` - Function to validate telemetry data
  - `success_by_default`: `bool` - Default success behavior
- **Note**: Automatically skips APM onboarding events

### `assert_seq_ids_are_roughly_sequential()`
- **Purpose**: Check that telemetry sequence IDs are roughly sequential
- **Usage**: Validates telemetry message ordering

### `assert_no_skipped_seq_ids()`
- **Purpose**: Ensure no telemetry sequence IDs are skipped
- **Usage**: Validates complete telemetry message delivery

## Remote Configuration Methods

### `validate_remote_configuration(validator, *, success_by_default=False)`
- **Purpose**: Validate remote configuration data
- **Parameters**:
  - `validator`: `Callable` - Function to validate remote config data
  - `success_by_default`: `bool` - Default success behavior

### `assert_rc_apply_state(product, config_id, apply_state)`
- **Purpose**: Check that a specific config has the expected apply state
- **Parameters**:
  - `product`: `str` - Product name
  - `config_id`: `str` - Configuration ID
  - `apply_state`: `RemoteConfigApplyState` - Expected apply state

### `assert_rc_capability(capability)`
- **Purpose**: Assert that a remote configuration capability is present
- **Parameters**:
  - `capability`: `Capabilities` - Capability to check for

### `assert_rc_targets_version_states(targets_version, config_states)`
- **Purpose**: Validate config states for a specific targets version
- **Parameters**:
  - `targets_version`: `int` - Version to check
  - `config_states`: `list` - Expected configuration states

### `wait_for_remote_config_request(timeout=30)`
- **Purpose**: Wait for a remote configuration request with non-empty client config
- **Parameters**:
  - `timeout`: `int` - Timeout in seconds (default: 30)

## Profiling & Headers Validation

### `validate_profiling(validator, *, success_by_default=False)`
- **Purpose**: Validate profiling data using a custom validator
- **Parameters**:
  - `validator`: `Callable` - Function to validate profiling data
  - `success_by_default`: `bool` - Default success behavior

### `assert_headers_presence(path_filter, request_headers=(), response_headers=(), check_condition=None)`
- **Purpose**: Validate the presence of HTTP headers in requests/responses
- **Parameters**:
  - `path_filter`: `Iterable[str] | str` - Path filters to check
  - `request_headers`: `Iterable[str]` - Headers to validate in requests
  - `response_headers`: `Iterable[str]` - Headers to validate in responses
  - `check_condition`: `Callable | None` - Additional condition function

## Best Practices

1. **Always use request filtering**: When possible, filter validations by specific requests to avoid false positives from other test activities.

2. **Use appropriate assertion methods**: Choose between `assert_*` methods (which raise exceptions) and `validate_*` methods (which use custom validators).

3. **Handle timing**: Use setup methods to generate traces before validation methods in test methods.

4. **Combine validations**: Multiple validation methods can be used together to comprehensively test tracer behavior.

5. **Check full traces when needed**: Use `full_trace=True` for validations that need to examine all spans in a trace, not just the triggering span.

## Common Patterns

### Basic Trace Validation
```python
def test_basic_tracing(self):
    r = weblog.get("/")
    interfaces.library.assert_trace_exists(r)
    interfaces.library.add_span_tag_validation(r, tags={"http.method": "GET"})
```

### AppSec Attack Detection
```python
def test_waf_attack(self):
    r = weblog.get("/", headers={"X-Attack": "' OR 1=1--"})
    interfaces.library.assert_waf_attack(r, rule="sqli-123")
```

### Custom Span Validation
```python
def test_custom_validation(self):
    r = weblog.get("/")

    def custom_validator(span):
        return span.get("service") == "my-service"

    interfaces.library.validate_spans(r, validator=custom_validator)
```

## Related Documentation

- [Library Interface Core Implementation](../../utils/interfaces/_library/core.py)
- [Interface Initialization](../../utils/interfaces/__init__.py)
- [End-to-End Testing Guide](../execute/README.md)
- [Adding New Tests](../edit/add-new-test.md)