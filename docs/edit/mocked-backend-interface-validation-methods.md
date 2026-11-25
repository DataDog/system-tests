# Mocked Backend Interface Validation Methods

`interfaces.mocked_backend` exposes what the [mocked backend](../mocked_backend/README.md) received: everything sent to the Datadog backend, by the agent, by an agentless library, or by the Lambda extension. Every end-to-end scenario uses it.

The requests are recorded as JSON files in `logs_<scenario_name>/interfaces/mocked_backend`, and decoded like the proxy does (msgpack, protobuf, gzip...). Each recorded request has its `path`, `host`, `query`, `request` (`headers`, `content`) and `response`.

## Usage Pattern

```python
from utils import interfaces, scenarios, weblog


@scenarios.default
class Test_Feature:
    def setup_main(self):
        self.r = weblog.get("/")

    def test_main(self):
        interfaces.mocked_backend.assert_trace_exists(self.r)

        for _, span in interfaces.mocked_backend.get_spans(self.r):
            assert span["service"] == "weblog"
```

## Provenance: `with_api_key`

Senders that must be told apart use their own fake API key (see `FakeDatadogKey`), e.g. serverless-init relaying what the weblog sends. `get_data` and the getters below take an optional `with_api_key`, to keep only what one sender sent. Get the key from the running scenario (e.g. `context.scenario.dd_api_key`, or `context.scenario.weblog_api_key` in agentless scenarios), never from `FakeDatadogKey` directly.

```python
for data in interfaces.mocked_backend.get_data("/api/v2/apmtelemetry", with_api_key=context.scenario.weblog_api_key):
    ...
```

## Methods

### Generic

- `get_data(path_filters=None, *, with_api_key=None)`: every recorded request, optionally filtered by path (a string, or a list of strings) and API key
- `validate_all(validator, path_filters=None, *, allow_no_data=False)`: run `validator(data)` on every matching request, and fail if one fails, or if there is no data (unless `allow_no_data`)
- `wait_for(wait_for_function, timeout)`: wait until `wait_for_function(data)` is true for a request, during the setup. Returns whether it happened
- `get_api_key(data)`: the API key a request was sent with

### Traces

- `get_traces(request=None, *, with_api_key=None)`: `(data, trace)` for every trace chunk sent to `/api/v0.2/traces`, optionally only those with a span of the weblog request. Legacy (`tracerPayloads`) and v1 (`idxTracerPayloads`) payloads give the same `DataDogAgentTrace`
- `get_spans(request=None, *, with_api_key=None)`: `(data, span)` for every span, optionally only those of the weblog request
- `get_spans_list(request, *, with_api_key=None)`: the spans of the weblog request, as a list
- `get_appsec_data(request, *, with_api_key=None)`: `(data, span, appsec_data)` for every span of the request carrying AppSec data (`_dd.appsec.json`, or meta struct)
- `assert_trace_exists(request, *, with_api_key=None)`: fail if no trace has a span of the weblog request

### Other products

- `get_telemetry_data(*, flatten_message_batches=True, with_api_key=None)`: telemetry sent to `/api/v2/apmtelemetry`. With `flatten_message_batches`, each payload of a `message-batch` is yielded as its own request
- `get_profiling_data(*, with_api_key=None)`: profiles sent to `/api/v2/profile`
- `get_metrics(*, with_api_key=None)`: `(data, point)` for every series sent to `/api/v2/series` or `/api/intake/metrics/v3/series`
- `get_sketches(*, with_api_key=None)`: `(data, point)` for every sketch sent to `/api/beta/sketches` or `/api/intake/metrics/v3/sketches`
- `get_stats(resource="", *, with_api_key=None)`: APM stats sent to `/api/v0.2/stats`, optionally only those of a resource (or a list of resources)
- `get_dsm_data(*, with_api_key=None)`: Data Streams Monitoring payloads sent to `/api/v0.1/pipeline_stats`

### Headers

- `assert_headers_presence(path_filter, request_headers=(), response_headers=(), check_condition=None)`: fail if a matching request lacks one of the headers. No matching request is not a failure

## What it is not

- It doesn't see what the library sends to the agent: use `interfaces.library` (see [library interface validation methods](./library-interface-validation-methods.md)).
- With an agent, the data has been processed by it: sampling, stats computation, obfuscation and rate limiting have been applied.
- It's not the real backend: nothing is processed, and it answers what it's told to (default responses, remote config, `MockedBackendResponse`). See the [mocked backend documentation](../mocked_backend/README.md).

## Related Documentation

- [Mocked backend](../mocked_backend/README.md)
- [Interface implementation](../../utils/interfaces/_mocked_backend.py)
- [Library interface validation methods](./library-interface-validation-methods.md)
- [Adding new tests](./add-new-test.md)
