# Parametric weblogs: HTTP interface

PARAMETRIC scenarios test the Datadog libraries through a small HTTP server, one per language, in `utils/build/docker/<language>/parametric/`.
The HTTP requests are sent by `ParametricTestClientApi`
([`utils/docker_fixtures/_test_clients/_test_client_parametric.py`](../../../utils/docker_fixtures/_test_clients/_test_client_parametric.py)):
most of its methods send one HTTP request to the server, which calls the library SDK. Tests don't use it directly:

* the `test_library` fixture is an `APMLibrary` (same file), which delegates to `ParametricTestClientApi`,
* span methods are on the span objects returned by `test_library` (`_TestSpan` and `_TestOtelSpan`, same file): for
  instance `span.set_meta()` calls `ParametricTestClientApi.span_set_meta()`, which sends `POST /trace/span/set_meta`.
  The `test_library.dd_start_span()` and `test_library.otel_start_span()` context managers also finish the span when
  they exit, with a second request (unless `end_on_exit=False` is given to `otel_start_span()`).

See [Parametric scenarios](../scenarios/parametric.md) for how the tests are written and run.

**Source of truth.** This document describes what the code does. If it disagrees with the code, the code wins, and this
document must be fixed:

* the client (`_test_client_parametric.py`) defines which endpoints the tests call, and with which payloads,
* the Python server ([`utils/build/docker/python/parametric/apm_test_client/server.py`](../../../utils/build/docker/python/parametric/apm_test_client/server.py))
  is the reference implementation: its request and response models are the reference schemas.

Not all languages implement every endpoint, or are up to spec with its parameters and return values: see the
[feature parity board](https://feature-parity.us1.prod.dog/#/?runDateFilter=7d&feature=339). A missing endpoint is
declared in the manifests, like any other missing feature.

## Server contract

### Startup

The server is started in a Docker container, on the network of the test agent, with these environment variables
(plus the `library_env` of the test, a `None` value removing the variable):

| Variable | Value |
|--|--|
| `APM_TEST_CLIENT_SERVER_PORT` | `8080`: the port the server must listen on |
| `DD_TRACE_AGENT_URL` | `http://<test agent container>:<port>` |
| `DD_AGENT_HOST`, `DD_TRACE_AGENT_PORT` | host and port of the test agent |
| `DD_TRACE_DEBUG` | `true` |
| `DD_TRACE_OTEL_ENABLED` | `true` |
| `SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS` | for `nodejs`, `java` and `php` only: extra arguments of the test (`library_extra_command_arguments`). Other languages receive them as command arguments. |

### Readiness

The client considers the server ready when `GET /non-existent-endpoint-to-ping-until-the-server-starts` returns **404**.
So the server must answer `404` to unknown paths. It gives up after 60 seconds, or as soon as the container stops.

### Requests and responses

* Requests and responses are JSON. Most endpoints are `POST`. A few `GET` endpoints also take a JSON body (see their
  request body below).
* Span ids and trace ids are integers. Endpoints acting on an existing span take its `span_id`.
* `GET /trace/crash` must crash the process: the client ignores the resulting connection error.
* Most client methods don't check the status code: they read fields of the JSON response, so an error response
  usually makes the test fail on a missing field. A few call `raise_for_status()` explicitly.

### Running the reference server

`./utils/scripts/parametric/run_reference_http.sh` runs the Python server on <http://localhost:8000>. Its OpenAPI
documentation is at <http://localhost:8000/docs>, and the schema at <http://localhost:8000/openapi.json> (to import in
Postman or another API client).

## Endpoints

Endpoints are grouped by feature. For each endpoint: the `ParametricTestClientApi` method(s) calling it, then the request and response
fields of the reference server. Types are the reference server ones; `X \| null` means the field is optional or nullable.

### Tracer configuration

#### `GET /trace/config`

Called by:

- `ParametricTestClientApi.config()`
- `ParametricTestClientApi.otel_effective_config()`: Read resolved OTLP exporter timeouts and BLRP settings from each SDK's configuration endpoint.

Request body:

_none_

Response:

| Field | Type | Required |
|--|--|--|
| `config` | dict[str, string \| null] | yes |

### Spans

#### `GET /trace/span/current`

Called by `ParametricTestClientApi.current_span()`.

Request body:

_none_

Response:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `trace_id` | integer | yes |

#### `GET /trace/span/get_all_baggage`

Called by `ParametricTestClientApi.span_get_all_baggage()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |

Response:

| Field | Type | Required |
|--|--|--|
| `baggage` | dict[str, string] | yes |

#### `GET /trace/span/get_baggage`

Called by `ParametricTestClientApi.span_get_baggage()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `key` | string | yes |

Response:

| Field | Type | Required |
|--|--|--|
| `baggage` | string | yes |

#### `POST /trace/span/add_event`

Called by `ParametricTestClientApi.span_add_event()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `name` | string | yes |
| `timestamp` | integer | yes |
| `attributes` | object | yes |

Response:

_empty object_

#### `POST /trace/span/add_link`

Called by `ParametricTestClientApi.span_add_link()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `parent_id` | integer | yes |
| `attributes` | object | yes |

Response:

_empty object_

#### `POST /trace/span/error`

Called by `ParametricTestClientApi.span_set_error()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `type` | string | yes |
| `message` | string | yes |
| `stack` | string | yes |

Response:

_empty object_

#### `POST /trace/span/extract_headers`

Called by `ParametricTestClientApi.dd_extract_headers()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `http_headers` | list[tuple[string, string]] | yes |

Response:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer |  |

#### `POST /trace/span/finish`

Called by `ParametricTestClientApi.finish_span()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |

Response:

_empty object_

#### `POST /trace/span/flush`

Called by `ParametricTestClientApi.dd_flush()`.

Request body:

_empty object_

Response:

_empty object_

#### `POST /trace/span/inject_headers`

Called by `ParametricTestClientApi.dd_inject_headers()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |

Response:

| Field | Type | Required |
|--|--|--|
| `http_headers` | list[tuple[string, string]] | yes |

#### `POST /trace/span/manual_drop`

Called by `ParametricTestClientApi.span_manual_drop()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |

Response:

_empty object_

#### `POST /trace/span/manual_keep`

Called by `ParametricTestClientApi.span_manual_keep()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |

Response:

_empty object_

#### `POST /trace/span/remove_all_baggage`

Called by `ParametricTestClientApi.span_remove_all_baggage()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |

Response:

_empty object_

#### `POST /trace/span/remove_baggage`

Called by `ParametricTestClientApi.span_remove_baggage()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `key` | string | yes |

Response:

_empty object_

#### `POST /trace/span/set_baggage`

Called by `ParametricTestClientApi.span_set_baggage()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `key` | string | yes |
| `value` | string | yes |

Response:

_empty object_

#### `POST /trace/span/set_meta`

Called by `ParametricTestClientApi.span_set_meta()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `key` | string | yes |
| `value` | string | yes |

Response:

_empty object_

#### `POST /trace/span/set_metric`

Called by `ParametricTestClientApi.span_set_metric()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `key` | string | yes |
| `value` | integer \| number | yes |

Response:

_empty object_

#### `POST /trace/span/set_resource`

Called by `ParametricTestClientApi.span_set_resource()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `resource` | string | yes |

Response:

_empty object_

#### `POST /trace/span/start`

Called by `ParametricTestClientApi.dd_start_span()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `name` | string | yes |
| `parent_id` | integer |  |
| `service` | string |  |
| `type` | string |  |
| `resource` | string |  |
| `span_tags` | list[tuple[string, string]] | yes |

Response:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `trace_id` | integer | yes |

### Statistics, remote config and agent interaction

#### `GET /trace/agent/ensure_agent_info`

Called by `ParametricTestClientApi.ensure_agent_info()`.

Request body:

_none_

Response:

_not declared by the reference server_

#### `GET /trace/crash`

Called by `ParametricTestClientApi.crash()`.

Request body:

_none_

Response:

_not declared by the reference server_

#### `POST /rc/start`

**Not called by the test client**: reference server only, not part of the interface.

Request body:

_none_

Response:

_not declared by the reference server_

#### `POST /rc/stop`

**Not called by the test client**: reference server only, not part of the interface.

Request body:

_none_

Response:

_not declared by the reference server_

#### `POST /trace/diagnostics/log_level`

Called by `ParametricTestClientApi.dd_log_level_diagnostics()`. Ask the app to trigger identifiable SDK warning and error diagnostics.

**Not implemented by the Python reference server**, see the client method for the exact request.

#### `POST /trace/remote-config/apply`

Called by `ParametricTestClientApi.flush_remote_config()`. Synchronously drain pending Remote Config and return the applied set.

Request body:

_empty object_

Response:

_not declared by the reference server_

#### `POST /trace/stats/flush`

Called by `ParametricTestClientApi.dd_flush_stats()`.

Request body:

_empty object_

Response:

_empty object_

### OpenTelemetry tracing

#### `GET /trace/otel/current_span`

Called by `ParametricTestClientApi.otel_current_span()`.

Request body:

_none_

Response:

_not declared by the reference server_

#### `POST /trace/otel/add_event`

Called by `ParametricTestClientApi.otel_add_event()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `name` | string | yes |
| `timestamp` | integer |  |
| `attributes` | object |  |

Response:

_empty object_

#### `POST /trace/otel/end_span`

Called by `ParametricTestClientApi.otel_end_span()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `id` | integer | yes |
| `timestamp` | integer |  |

Response:

_not declared by the reference server_

#### `POST /trace/otel/flush`

Called by `ParametricTestClientApi.otel_flush()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `seconds` | integer |  |

Response:

_not declared by the reference server_

#### `POST /trace/otel/is_recording`

Called by `ParametricTestClientApi.otel_is_recording()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |

Response:

_not declared by the reference server_

#### `POST /trace/otel/otel_set_baggage`

Called by `ParametricTestClientApi.otel_set_baggage()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `key` | string | yes |
| `value` | string | yes |

Response:

| Field | Type | Required |
|--|--|--|
| `value` | string | yes |

#### `POST /trace/otel/record_exception`

Called by `ParametricTestClientApi.otel_record_exception()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `message` | string | yes |
| `attributes` | object | yes |

Response:

_empty object_

#### `POST /trace/otel/set_attributes`

Called by `ParametricTestClientApi.otel_set_attributes()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

#### `POST /trace/otel/set_name`

Called by `ParametricTestClientApi.otel_set_name()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `name` | string | yes |

Response:

_not declared by the reference server_

#### `POST /trace/otel/set_status`

Called by `ParametricTestClientApi.otel_set_status()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |
| `code` | string | yes |
| `description` | string | yes |

Response:

_not declared by the reference server_

#### `POST /trace/otel/span_context`

Called by `ParametricTestClientApi.otel_get_span_context()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `span_id` | integer | yes |

Response:

_not declared by the reference server_

#### `POST /trace/otel/start_span`

Called by `ParametricTestClientApi._otel_trace_start_span()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `name` | string | yes |
| `parent_id` | integer |  |
| `span_kind` | integer |  |
| `timestamp` | integer |  |
| `links` | list[object] | yes |
| `events` | list[object] | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

### OpenTelemetry metrics and logs

#### `GET /otel/effective_config`

Called by `ParametricTestClientApi.otel_effective_config()`, for Node.js only (other languages use `GET /trace/config`).
Read resolved OTLP exporter timeouts and BLRP settings.

**Not implemented by the Python reference server**: see
[Effective OpenTelemetry configuration](../scenarios/parametric.md#effective-opentelemetry-configuration).

#### `POST /log/otel/flush`

Called by `ParametricTestClientApi.otel_logs_flush()`. Flush all OpenTelemetry logs and get provider information.

Request body:

| Field | Type | Required |
|--|--|--|
| `seconds` | integer | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/counter_add`

Called by `ParametricTestClientApi.otel_counter_add()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `unit` | string | yes |
| `description` | string | yes |
| `value` | integer \| number | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/create_asynchronous_counter`

Called by `ParametricTestClientApi.otel_create_asynchronous_counter()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `description` | string | yes |
| `unit` | string | yes |
| `value` | integer \| number | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/create_asynchronous_gauge`

Called by `ParametricTestClientApi.otel_create_asynchronous_gauge()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `description` | string | yes |
| `unit` | string | yes |
| `value` | integer \| number | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/create_asynchronous_updowncounter`

Called by `ParametricTestClientApi.otel_create_asynchronous_updowncounter()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `description` | string | yes |
| `unit` | string | yes |
| `value` | integer \| number | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/create_counter`

Called by `ParametricTestClientApi.otel_create_counter()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `description` | string | yes |
| `unit` | string | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/create_gauge`

Called by `ParametricTestClientApi.otel_create_gauge()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `description` | string | yes |
| `unit` | string | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/create_histogram`

Called by `ParametricTestClientApi.otel_create_histogram()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `description` | string | yes |
| `unit` | string | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/create_updowncounter`

Called by `ParametricTestClientApi.otel_create_updowncounter()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `description` | string | yes |
| `unit` | string | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/force_flush`

Called by `ParametricTestClientApi.otel_metrics_force_flush()`.

Request body:

_empty object_

Response:

_not declared by the reference server_

#### `POST /metrics/otel/gauge_record`

Called by `ParametricTestClientApi.otel_gauge_record()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `unit` | string | yes |
| `description` | string | yes |
| `value` | integer \| number | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/get_meter`

Called by `ParametricTestClientApi.otel_get_meter()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `name` | string | yes |
| `version` | string |  |
| `schema_url` | string |  |
| `attributes` | object |  |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/histogram_record`

Called by `ParametricTestClientApi.otel_histogram_record()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `unit` | string | yes |
| `description` | string | yes |
| `value` | integer \| number | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/set_asynchronous_observations`

Called by `ParametricTestClientApi.otel_set_asynchronous_observations()`.
Replace the observations reported by the callback of an asynchronous instrument created by a `create_asynchronous_*`
endpoint. `kind` is `counter`, `updowncounter` or `gauge`. Each observation has a `value` (integer \| number) and
`attributes` (object).

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `kind` | string | yes |
| `name` | string | yes |
| `unit` | string | yes |
| `description` | string | yes |
| `observations` | list[OtelAsynchronousObservation] | yes |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/shutdown`

Called by `ParametricTestClientApi.otel_metrics_shutdown()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `seconds` | integer |  |

Response:

_not declared by the reference server_

#### `POST /metrics/otel/updowncounter_add`

Called by `ParametricTestClientApi.otel_updowncounter_add()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `meter_name` | string | yes |
| `name` | string | yes |
| `unit` | string | yes |
| `description` | string | yes |
| `value` | integer \| number | yes |
| `attributes` | object | yes |

Response:

_not declared by the reference server_

#### `POST /otel/logger/create`

Called by `ParametricTestClientApi.create_logger()`. Create an OpenTelemetry logger with the specified name and optional parameters.

Request body:

| Field | Type | Required |
|--|--|--|
| `name` | string | yes |
| `level` | string | yes |
| `version` | string |  |
| `schema_url` | string |  |
| `attributes` | object |  |

Response:

| Field | Type | Required |
|--|--|--|
| `success` | boolean | yes |

#### `POST /otel/logger/write`

Called by `ParametricTestClientApi.write_log()`. Generate a log message with the specified parameters.

Request body:

| Field | Type | Required |
|--|--|--|
| `message` | string | yes |
| `level` | string | yes |
| `logger_name` | string | yes |
| `span_id` | integer |  |

Response:

| Field | Type | Required |
|--|--|--|
| `success` | boolean | yes |

### Feature flags (FFE)

#### `POST /ffe`

**Not called by the test client**: reference server only, not part of the interface.

Request body:

_none_

Response:

_not declared by the reference server_

#### `POST /ffe/evaluate`

Called by `ParametricTestClientApi.ffe_evaluate()`. Evaluate a feature flag.

Request body (not declared by the reference server, which reads the raw request; fields sent by the client):

| Field | Type | Required |
|--|--|--|
| `flag` | string | yes |
| `variationType` | string: `BOOLEAN`, `STRING`, `INTEGER`, `NUMERIC` or `JSON` | yes |
| `defaultValue` | boolean \| string \| number \| object | yes |
| `targetingKey` | string \| null | yes |
| `attributes` | object | yes |
| `span_id` | string: id of a span to activate during the evaluation | no |
| `exposureHooks` | boolean: `true` to capture two exposure hook observations | no |
| `failAfterHook` | boolean: `true` to reject the result in an After hook (requires `exposureHooks`) | no |

Response: not declared by the reference server. It contains `value`, `reason`, `errorCode`, `providerStatus`
(see [Feature Flag evaluation provider status](../scenarios/parametric.md#feature-flag-evaluation-provider-status)),
and `exposureHooks` when requested.

#### `POST /ffe/fetch-rules-configuration`

Called by `ParametricTestClientApi.ffe_fetch_rules_configuration()`. Fetch and serialize portable rules in a process without tracer/provider initialization.

**Not implemented by the Python reference server**. The request body is the `options` object of the test: see
[Standalone Rules Configuration](../scenarios/parametric.md#standalone-rules-configuration).

#### `POST /ffe/start`

Called by `ParametricTestClientApi.ffe_start()`. Initialize the FFE (Feature Flagging & Experimentation) provider.

Request body (not declared by the reference server, which reads the raw request; fields sent by the client):

| Field | Type | Required |
|--|--|--|
| `configuration` | object | no |
| `flag_selection` | any: passed untouched to the flag selection option of the SDK | no |

Response:

_not declared by the reference server_

### LLM Observability

#### `POST /llm_observability/dataset/create`

Called by `ParametricTestClientApi.llmobs_dataset_create()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `dataset_name` | string | yes |
| `description` | string |  |
| `records` | list[DatasetRecordRequest] |  |
| `project_name` | string |  |

Response:

_not declared by the reference server_

#### `POST /llm_observability/dataset/delete`

Called by `ParametricTestClientApi.llmobs_dataset_delete()`.

Request body:

| Field | Type | Required |
|--|--|--|
| `dataset_id` | string | yes |

Response:

_not declared by the reference server_

#### `POST /llm_observability/trace`

Called by `ParametricTestClientApi.llmobs_trace()`. Send a trace structure request to the LLM Observability endpoint.

Request body:

| Field | Type | Required |
|--|--|--|
| `trace_structure_request` | LlmObsAnnotationContextRequest \| LlmObsSpanRequest \| ApmSpanRequest | yes |

Response:

_not declared by the reference server_

