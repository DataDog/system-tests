# Progress

## Status
In Progress

## Tasks

## Files Changed

## Notes

### span_sampling worker (sss016/017/018) — OMITTED, no cases ported
- All three are upstream `@missing_feature` for BOTH nodejs and python (the only
  two libraries verified here): nodejs "Not implemented"; python "RPC issue
  causing test to hang". A case skipped on both libs has zero dual-verify value.
- They test the tracer-side **dropping policy** (client-side p0 drop), which is
  gated by the test-agent advertising `client_drop_p0s` (`test_agent.info()`)
  and asserted via spans delivered to the agent (`wait_for_num_traces` /
  `len(trace)`). The in-memory capture seam has no test-agent and captures at
  the exporter, so dropping is not modelable.
- Empirically confirmed: with the sss018 env (DD_TRACE_SAMPLE_RATE=0, dropping
  policy on), upstream expects 0 spans delivered; the in-memory model captures 2.
- The agent-independent parts of sss016/sss017 (SSS tags on the selected
  root/child span) duplicate already-ported sss014/sss015.
- Decision: OMIT (sanctioned omission path). No new file, no registration, no
  commit. Needs the deferred test-agent capture seam to ever be portable.

## worker: headers_none (branch bengl/redux-none, commit ae15392ab)
Ported 4 headers_none cases (src/headers_none_more.temper + cases.temper). All
dual-verified (js+py PASS) and env-real (fail with no env, verified via run-one):
- headers_none.inject
- headers_none.inject_with_other_propagators (strengthened: asserts no traceparent/tracestate so it's env-real)
- headers_none.propagate
- headers_none.single_key_propagate
Worktree totals: js 187/187 (25 skip), py 205/205 (7 skip). Committed src/ only.
