# TODO

- [ ] No telemetry emitter in production should set `dd-telemetry-debug-enabled: true`.
  `dd-trace-py` currently emits telemetry with `dd-telemetry-debug-enabled: true` from the native/libdatadog-backed path. This should be treated as a production bug and fixed so prod telemetry always reports debug disabled unless explicitly running in a debug/test mode.

- [ ] Enforce a single telemetry emitter per tracer runtime-id.
  `dd-trace-py` currently has two emitters active for the same runtime-id:
  1) the Python telemetry writer (`DD-Session-ID`/`DD-Telemetry-*` headers, `debug: false` payload style), and
  2) the native exporter telemetry path (`user-agent: telemetry/4.0.0`, lowercase `dd-telemetry-*` headers, `src_library:libdatadog` metrics, debug enabled).
  This violates prior telemetry contract/spec expectations and creates overlapping/ambiguous seq_id streams that break assumptions in system-tests.
