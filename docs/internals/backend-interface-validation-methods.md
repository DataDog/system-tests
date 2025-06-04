# Backend Interface Validation Methods

This document provides a comprehensive overview of all validation methods available in the `_BackendInterfaceValidator` class. The backend interface validates data by making API calls directly to the Datadog Backend to verify that traces, spans, metrics, and logs have been properly received and processed.

## Overview

The `_BackendInterfaceValidator` is instantiated as a singleton in `utils/interfaces/__init__.py` and can be accessed as `interfaces.backend` in your test cases. Unlike the library and agent interfaces that validate intercepted messages, the backend interface makes direct API calls to the Datadog backend to verify data has been properly ingested and is available through the platform.

## Key Characteristics

- **Direct API calls**: Makes actual HTTP requests to Datadog's production APIs
- **End-to-end validation**: Verifies data has successfully traversed the entire pipeline
- **Authentication required**: Requires `DD_API_KEY` and `DD_APP_KEY` environment variables
- **Rate limiting aware**: Handles Datadog API rate limits automatically
- **Multi-site support**: Supports all Datadog sites (US, EU, Gov, etc.)

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
        # Verify traces reach the backend
        traces = interfaces.backend.assert_library_traces_exist(self.r)
        assert len(traces) >= 1
        
        # Verify spans are searchable
        spans = interfaces.backend.assert_request_spans_exist(
            self.r, "service:weblog", min_spans_len=1
        )
        assert len(spans) >= 1
```

## Environment Setup

Before using the backend interface, ensure you have the required environment variables:

```bash
export DD_API_KEY="your_api_key"
export DD_APP_KEY="your_application_key"  # or DD_APPLICATION_KEY
export DD_SITE="datadoghq.com"  # or your specific site
```

Supported DD_SITE values:
- `datad0g.com` (default)
- `datadoghq.com`
- `datadoghq.eu`
- `ddog-gov.com`
- `us3.datadoghq.com`
- `us5.datadoghq.com`

## Trace Validation Methods

### `assert_library_traces_exist(request, min_traces_len=1)`
- **Purpose**: Verify that traces from the library/tracer reach the Datadog backend
- **Parameters**:
  - `request`: `HttpResponse` - Request that generated the traces
  - `min_traces_len`: `int` - Minimum number of traces expected (default: 1)
- **Returns**: List of trace dictionaries from the backend
- **Usage**: End-to-end validation that traces are ingested
- **API**: Uses `/api/v1/trace/{trace_id}` endpoint

### `assert_otlp_trace_exist(request, dd_trace_id, dd_api_key=None, dd_app_key=None)`
- **Purpose**: Verify that OpenTelemetry traces reach the backend with a specific trace ID
- **Parameters**:
  - `request`: `HttpResponse` - Request that generated the trace
  - `dd_trace_id`: `int` - Datadog trace ID to verify
  - `dd_api_key`: `str | None` - Optional API key override
  - `dd_app_key`: `str | None` - Optional application key override
- **Returns**: Trace dictionary from the backend
- **Usage**: Validate OpenTelemetry integration specifically

## Span Search Methods

### `assert_spans_exist(query_filter, min_spans_len=1, limit=100, retries=5)`
- **Purpose**: Search for spans using the Event Platform with a custom query
- **Parameters**:
  - `query_filter`: `str` - Search query (same format as UI trace search)
  - `min_spans_len`: `int` - Minimum number of spans expected
  - `limit`: `int` - Maximum number of spans to return
  - `retries`: `int` - Number of retry attempts
- **Returns**: List of span event dictionaries
- **Usage**: Flexible span searching with custom filters
- **API**: Uses Event Platform analytics API

### `assert_request_spans_exist(request, query_filter, min_spans_len=1, limit=100, retries=5)`
- **Purpose**: Search for spans related to a specific request with additional filters
- **Parameters**:
  - `request`: `HttpResponse` - Request to filter spans by
  - `query_filter`: `str` - Additional search criteria
  - `min_spans_len`: `int` - Minimum number of spans expected
  - `limit`: `int` - Maximum number of spans to return
  - `retries`: `int` - Number of retry attempts
- **Returns**: List of span event dictionaries
- **Usage**: Combine request filtering with custom search criteria
- **Note**: Automatically adds request ID to the query filter

### `assert_single_spans_exist(request, min_spans_len=1, limit=100)`
- **Purpose**: Verify that single span events exist for a specific request
- **Parameters**:
  - `request`: `HttpResponse` - Request that should have generated single spans
  - `min_spans_len`: `int` - Minimum number of single spans expected
  - `limit`: `int` - Maximum number of spans to return
- **Returns**: List of single span event dictionaries
- **Usage**: Validate single span instrumentation
- **Filter**: Automatically searches for `@single_span:true`

## Metrics Validation Methods

### `query_timeseries(rid, start, end, metric, dd_api_key=None, dd_app_key=None, retries=12, sleep_interval_multiplier=2.0, initial_delay_s=10.0)`
- **Purpose**: Query metric timeseries data from the backend
- **Parameters**:
  - `rid`: `str` - Request ID to filter metrics
  - `start`: `int` - Start time (Unix timestamp)
  - `end`: `int` - End time (Unix timestamp)
  - `metric`: `str` - Metric name to query
  - `dd_api_key`: `str | None` - Optional API key override
  - `dd_app_key`: `str | None` - Optional application key override
  - `retries`: `int` - Number of retry attempts
  - `sleep_interval_multiplier`: `float` - Multiplier for retry delay
  - `initial_delay_s`: `float` - Initial delay before first attempt
- **Returns**: Metric series data from backend
- **Usage**: Validate custom metrics ingestion
- **API**: Uses `/api/v1/query` endpoint
- **Note**: Metrics take longer to be available, hence the initial delay

## Logs Validation Methods

### `get_logs(query, rid, dd_api_key=None, dd_app_key=None, retries=10, sleep_interval_multiplier=2.0)`
- **Purpose**: Search for logs in the backend using a query
- **Parameters**:
  - `query`: `str` - Log search query
  - `rid`: `str` - Request ID to validate in logs
  - `dd_api_key`: `str | None` - Optional API key override
  - `dd_app_key`: `str | None` - Optional application key override
  - `retries`: `int` - Number of retry attempts
  - `sleep_interval_multiplier`: `float` - Multiplier for retry delay
- **Returns**: Log entry dictionary if found
- **Usage**: Validate log ingestion and content
- **API**: Uses `/api/v2/logs/events` endpoint

## Key Features

### Automatic Request ID Association
The backend interface automatically associates traces with requests using the request ID (rid) propagated in the User-Agent header. This enables:
- Precise filtering of data related to specific test requests
- Avoiding interference from other concurrent tests
- Accurate validation of end-to-end data flow

### Rate Limiting Handling
The interface automatically handles Datadog API rate limits:
- Detects `429 Too Many Requests` responses
- Sleeps according to `x-ratelimit-reset` header
- Automatically retries after rate limit expires

### Multi-Site Support
Supports all Datadog sites with automatic URL resolution:
```python
# Automatically resolves to correct API endpoint based on DD_SITE
# datad0g.com → https://dd.datad0g.com
# datadoghq.com → https://app.datadoghq.com
# datadoghq.eu → https://app.datadoghq.eu
```

### Retry Logic
Built-in retry mechanisms for eventual consistency:
- Traces: 5 retries with exponential backoff
- Spans: 5 retries with exponential backoff
- Metrics: 12 retries with initial 10s delay
- Logs: 10 retries with exponential backoff

## Best Practices

1. **Set appropriate timeouts**: Backend validation takes longer than interface validation
2. **Use specific queries**: More specific span queries reduce false positives
3. **Handle eventual consistency**: Backend data may take time to be available
4. **Monitor rate limits**: High-frequency tests may hit API rate limits
5. **Use request filtering**: Always filter by request when possible

## Common Patterns

### Basic End-to-End Validation
```python
def test_end_to_end_trace_ingestion(self):
    r = weblog.get("/")
    
    # Verify traces reach backend
    traces = interfaces.backend.assert_library_traces_exist(r)
    assert len(traces) == 1
    
    # Verify trace structure
    trace = traces[0]
    assert len(trace) > 0  # Has spans
    assert trace[0]["service"] == "weblog"
```

### Span Search Validation
```python
def test_span_search(self):
    r = weblog.get("/user/123")
    
    # Search for spans with specific resource
    spans = interfaces.backend.assert_request_spans_exist(
        r, 
        query_filter="@http.url_details.path:/user/* @http.method:GET",
        min_spans_len=1
    )
    
    # Validate span content
    assert any(span["content"]["resource"] == "GET /user/123" for span in spans)
```

### OpenTelemetry Validation
```python
def test_otlp_trace_ingestion(self):
    # Get OTEL trace ID from OpenTelemetry interface
    r = weblog.get("/")
    otel_trace_ids = list(interfaces.open_telemetry.get_otel_trace_id(r))
    assert len(otel_trace_ids) == 1
    
    # Verify it reaches the backend
    trace = interfaces.backend.assert_otlp_trace_exist(r, otel_trace_ids[0])
    assert trace is not None
```

### Metrics Validation
```python
def test_custom_metric_ingestion(self):
    import time
    
    start_time = int(time.time()) - 300  # 5 minutes ago
    end_time = int(time.time())
    
    r = weblog.get("/")
    rid = r.get_rid()
    
    # Query for custom metric
    series = interfaces.backend.query_timeseries(
        rid=rid,
        start=start_time,
        end=end_time,
        metric="custom.metric.name"
    )
    
    assert len(series["series"]) > 0
```

### Single Span Validation
```python
def test_single_span_instrumentation(self):
    r = weblog.get("/single-span-endpoint")
    
    # Verify single spans are created
    single_spans = interfaces.backend.assert_single_spans_exist(r, min_spans_len=1)
    
    # Validate single span properties
    assert len(single_spans) >= 1
    for span in single_spans:
        assert span["content"]["meta"]["_dd.span_type"] == "single_span"
```

### Log Validation
```python
def test_log_ingestion(self):
    r = weblog.get("/")
    rid = r.get_rid()
    
    # Search for application logs
    log = interfaces.backend.get_logs(
        query=f"service:weblog status:info",
        rid=rid
    )
    
    assert log is not None
    assert "weblog" in log["attributes"]["service"]
```

## Data Flow Understanding

The backend interface validates at the final stage of the pipeline:

```
[Tracer] → [Agent] → [Backend] → [APIs]
                                    ↑
                             Backend Interface
                             (validates here)
```

This means:
- Data has been fully processed and ingested
- All transformations, sampling, and aggregations are complete
- Data is available through production APIs
- Search indices have been updated

## Common Use Cases

1. **End-to-End Validation**: Ensure complete data pipeline functionality
2. **Search Functionality**: Verify data is properly indexed and searchable
3. **API Integration**: Test that data is available through public APIs
4. **Cross-Product Validation**: Verify data appears in APM, Logs, Metrics, etc.
5. **Customer Experience**: Validate what customers would see in the UI

## Troubleshooting

### Authentication Issues
```
ValueError: Request to the backend returned error 403
```
- Check `DD_API_KEY` and `DD_APP_KEY` environment variables
- Verify keys have appropriate permissions
- Ensure keys are valid for the specified `DD_SITE`

### Data Not Found
```
ValueError: Backend did not provide trace after N retries
```
- Increase retry count for eventual consistency
- Check if data was actually generated (use library/agent interfaces)
- Verify request ID propagation is working

### Rate Limiting
The interface handles rate limits automatically, but you may see warnings:
```
Rate limit hit, sleeping N seconds
```
- This is normal for high-frequency tests
- Consider reducing test frequency if persistent

## Related Documentation

- [Backend Interface Core Implementation](../../utils/interfaces/_backend.py)
- [Interface Initialization](../../utils/interfaces/__init__.py)
- [Library Interface Validation Methods](./library-interface-validation-methods.md)
- [Agent Interface Validation Methods](./agent-interface-validation-methods.md)
- [End-to-End Testing Guide](../execute/README.md)
- [Datadog API Documentation](https://docs.datadoghq.com/api/latest/) 