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

## Methods

### Data Retrieval Methods
- `get_traces(request=None)` - Get all traces, optionally filtered by request ID
- `get_spans(request=None, *, full_trace=False)` - Iterate over spans with flexible filtering options
- `get_root_spans(request=None)` - Get only root spans (spans with no parent), optionally filtered by request
- `get_root_span(request)` - Get exactly one root span for a request (fails if 0 or >1 found)
- `get_appsec_events(request=None, *, full_trace=False)` - Get AppSec events from trace spans
- `get_legacy_appsec_events(request=None)` - Get legacy AppSec events from dedicated endpoints
- `get_telemetry_data(*, flatten_message_batches=True)` - Get telemetry data from agent
- `get_telemetry_metric_series(namespace, metric)` - Get specific telemetry metric series by namespace and metric name
- `get_profiling_data()` - Get profiling data from `/profiling/v1/input` endpoint

### Trace & Span Validation Methods
- `add_span_tag_validation(request=None, tags=None, *, value_as_regular_expression=False, full_trace=False)` - Validate specific span tags with optional regex support
- `assert_trace_exists(request, span_type=None)` - Assert trace exists for request, optionally filtered by span type
- `assert_trace_id_uniqueness()` - Ensure all trace IDs are unique across all traces
- `assert_receive_request_root_trace()` - Assert at least one web request root trace was received

### AppSec Validation Methods
- `validate_all_appsec(request=None, validator=None, *, legacy_validator=None, full_trace=False)` - General AppSec event validation with modern and legacy support
- `assert_waf_attack(request, rule=None, pattern=None, value=None, address=None, patterns=None, key_path=None, *, full_trace=False, span_validator=None)` - Assert WAF detected attack with flexible matching criteria
- `assert_rasp_attack(request, rule, parameters=None)` - Assert RASP detected attack with specific rule and parameters
- `assert_no_appsec_event(request)` - Assert no AppSec events were generated for request
- `add_appsec_reported_header(request, header_name)` - Validate specific header was reported in AppSec events
- `assert_iast_implemented()` - Assert IAST is implemented (checks for `_dd.iast.enabled` in span metadata)

### Telemetry Validation Methods
- `validate_telemetry(validator)` - Validate telemetry data using custom validator (auto-skips APM onboarding events)
- `assert_seq_ids_are_roughly_sequential()` - Check telemetry sequence IDs are roughly sequential
- `assert_no_skipped_seq_ids()` - Ensure no telemetry sequence IDs are skipped

### Remote Configuration Methods
- `validate_remote_configuration(validator)` - Validate remote configuration data with custom validator
- `assert_rc_apply_state(product, config_id, apply_state)` - Check specific config has expected apply state
- `assert_rc_capability(capability)` - Assert remote configuration capability is present
- `assert_rc_targets_version_states(targets_version, config_states)` - Validate config states for specific targets version
- `wait_for_remote_config_request(timeout=30)` - Wait for remote config request with non-empty client config

### Profiling & Headers Validation
- `validate_profiling(validator)` - Validate profiling data using custom validator
- `assert_headers_presence(path_filter, request_headers=(), response_headers=(), check_condition=None)` - Validate presence of HTTP headers in requests/responses

## Best Practices

1. **Always use request filtering**: When possible, filter validations by specific requests to avoid false positives from other test activities
2. **Use appropriate assertion methods**: Choose between `assert_*` methods (which raise exceptions) and `validate_*` methods (which use custom validators)
3. **Handle timing**: Use setup methods to generate traces before validation methods in test methods
4. **Combine validations**: Multiple validation methods can be used together to comprehensively test tracer behavior
5. **Check full traces when needed**: Use `full_trace=True` for validations that need to examine all spans in a trace, not just the triggering span

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