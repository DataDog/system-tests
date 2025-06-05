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

## Methods

### Trace Validation Methods
- `assert_library_traces_exist(request, min_traces_len=1)` - Verify traces from library reach backend via `/api/v1/trace/{trace_id}`
- `assert_otlp_trace_exist(request, dd_trace_id, dd_api_key=None, dd_app_key=None)` - Verify OpenTelemetry traces reach backend with specific trace ID

### Span Search Methods
- `assert_spans_exist(query_filter, min_spans_len=1, limit=100, retries=5)` - Search spans using Event Platform with custom query
- `assert_request_spans_exist(request, query_filter, min_spans_len=1, limit=100, retries=5)` - Search spans for specific request with additional filters
- `assert_single_spans_exist(request, min_spans_len=1, limit=100)` - Verify single span events exist for request (auto-searches `@single_span:true`)

### Metrics Validation Methods
- `query_timeseries(rid, start, end, metric, dd_api_key=None, dd_app_key=None, retries=12, sleep_interval_multiplier=2.0, initial_delay_s=10.0)` - Query metric timeseries data via `/api/v1/query`

### Logs Validation Methods
- `get_logs(query, rid, dd_api_key=None, dd_app_key=None, retries=10, sleep_interval_multiplier=2.0)` - Search logs via `/api/v2/logs/events` with query and request ID

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