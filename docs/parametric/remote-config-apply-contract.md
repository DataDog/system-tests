# Parametric Harness: `/trace/remote-config/apply` Contract

Owner: APM SDK Capabilities
Status: pilot (Python only as of this writing)
See also: `tests/parametric/test_dynamic_configuration.py::set_and_wait_rc`,
`tests/parametric/test_remote_config_apply_endpoint.py`

## Why this exists

`set_and_wait_rc()` originally waited only for the test-agent to report an
`APM_TRACING ACKNOWLEDGED` from the tracer. That ACK fires when the RC client
has received and validated the payload — **not** when the tracer's subscribers
have actually applied it. The gap is small for in-process tracers (Python, Go,
Java, Node.js, .NET, Ruby, Rust) and large for out-of-process ones (PHP via
sidecar). Tests that read tracer state immediately after the ACK flake on the
small gap and reliably fail on the large one.

This endpoint closes the gap by giving tests a synchronous, deterministic
"process pending RC now" call. `set_and_wait_rc()` now calls this endpoint
internally after the ACK on tracers that implement it (see
`_RC_APPLY_ENDPOINT_LANGS`), so callers do not need to invoke it explicitly.

## Endpoint

- Method: `POST`
- Path: `/trace/remote-config/apply`
- Content-Type: `application/json`
- Request body: `{}` (no required fields; reserved for future per-`config_id` semantics)
- Response: `application/json`, `200 OK` on success, `504` on timeout

### Response schema (success)

```json
{
  "applied_configs": [
    {"config_id": "<id>", "product": "APM_TRACING"}
  ]
}
```

`applied_configs` is the list of configs the tracer believes are currently
applied after the synchronous drain. May be empty if no RC has been received
yet — that is **not** an error.

### Response schema (timeout)

```json
{"error": "timeout waiting for remote config to apply", "timeout_seconds": 10.0}
```

`504 Gateway Timeout` status. The server may set its own default timeout; 10
seconds is the recommended default (PHP's sidecar can take several seconds to
drain).

## Semantics

When called, the parametric server MUST:

1. Synchronously fetch any pending RC from the test agent (i.e. perform one
   `request` poll cycle, not wait for the next periodic tick).
2. Synchronously dispatch any received payloads to all registered product
   callbacks (samplers, etc.), so that by the time the call returns, the
   tracer's in-memory state reflects the latest RC.
3. Return the list of currently-applied configs.

The endpoint MUST be idempotent: calling it repeatedly with no new RC pending
is a no-op that returns the current applied set.

The endpoint MUST apply **all** pending RC products, not just `APM_TRACING`.
Filtering by product can be added later as a request-body field if needed.

The endpoint MUST NOT block forever. The server enforces a timeout (default
10s). If the underlying primitives haven't returned by then, respond `504`.

## Per-language implementation notes

### Python (reference implementation)

dd-trace-py exposes the primitives directly. The synchronous chain is:

```python
from ddtrace.internal.remoteconfig.worker import remoteconfig_poller
client = remoteconfig_poller._client
client.request()                       # fetch + publish to connector
client._global_subscriber.periodic()   # drain connector, invoke callbacks
```

No dd-trace-py changes required.

### Go

Likely `internal/remoteconfig.Client.poll()` or equivalent. Investigate whether
poll already calls subscriber callbacks inline; if so, one call is enough.

### Java

Likely `ConfigurationPoller.poll()` synchronous variant. Check whether
`SharedCommunicationObjects` exposes a synchronous drain.

### Node.js

Likely `packages/dd-trace/src/remote_config/index.js` — check for a
synchronous `poll`/`update` method.

### .NET

Investigate `Datadog.Trace.RemoteConfigurationManagement.RemoteConfigurationManager`
for a synchronous variant.

### Ruby

Investigate `Datadog::Core::Remote::Component#sync` or the polling worker
for a synchronous variant. See also `03-ruby-rc-bootstrap-plan.md` in this
same report directory for related Ruby RC bootstrap work.

### Rust

Investigate `datadog-remote-config` crate. See `02-rust-implementation-plan.md`
in this same report directory.

### C++

Investigate the dd-trace-cpp RC poller.

### PHP (motivator)

This is the most important case. The PHP sidecar ACKs as soon as a payload
lands in shared memory, but the PHP request process applies it lazily on the
next request boundary. The endpoint implementation needs to:

1. Synchronously trigger the sidecar to fetch from the test-agent.
2. Synchronously trigger the PHP-side apply (likely a new
   `dd_trace_internal_fn("process_remote_config_now")` or equivalent that
   reads the sidecar's shared memory and applies it on the current request).

This is by far the largest per-language lift and is the reason this endpoint
exists. Coordinate with the PHP tracer team before starting.

## Test-framework helper

The Python test framework exposes the low-level call:

```python
test_library.flush_remote_config(timeout: float = 10.0) -> list[dict]
```

and the high-level helper that tests use directly:

```python
set_and_wait_rc(test_agent, test_library, config_overrides, config_id=None)
```

`set_and_wait_rc()` waits for the test-agent ACK and then, on tracers in
`_RC_APPLY_ENDPOINT_LANGS`, calls `flush_remote_config()` to synchronously
drain pending RC. Tracers outside the allowlist get the ACK-only path with
no behavior change.

## Adoption

For tracers that have not yet implemented the endpoint, `set_and_wait_rc()`
falls back to the ACK-only path automatically. Add the tracer's language to
`_RC_APPLY_ENDPOINT_LANGS` once the endpoint is implemented; no test changes
are required. The probabilistic retry loop inside `get_sampled_trace()`
remains (it handles sampling-by-chance, not the RC race).

## Open questions

- **Idempotency under concurrent calls?** The endpoint is single-threaded per
  FastAPI worker, so concurrent calls serialize naturally. If a tracer's
  underlying primitives are not thread-safe, the implementation must add a
  lock.
- **What if the test agent is unreachable?** `request()` returns `False`. The
  endpoint should still return `200` with whatever applied_configs are
  currently in memory — the contract is "drain what you can," not "guarantee
  fresh fetch."
- **Empty response when no RC ever received?** Returns `200` with
  `{"applied_configs": []}`. Not a 404 — this is a normal state during early
  test setup.
