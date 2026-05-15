# Feature: `force_execute` input

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `.github/workflows/run-end-to-end.yml` line 113 — sets `SYSTEM_TESTS_FORCE_EXECUTE`
- `.github/workflows/run-parametric.yml` line 97 — same

`force_execute` is a comma-separated list of test node IDs that are forced to run
regardless of xfail or skip markers. The run scripts consume it via the
`SYSTEM_TESTS_FORCE_EXECUTE` environment variable.

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   force_execute:
     description: "Comma-separated test node IDs to force-execute"
     default: ""
   ```
2. Add a `variables` block to `run_test_pipeline` to forward the value to the child
   pipeline:
   ```yaml
   run_test_pipeline:
     variables:
       SYSTEM_TESTS_FORCE_EXECUTE: "$[[ inputs.force_execute ]]"
     trigger:
       ...
   ```
   The existing run job template (`system-tests.yml`) already calls `./run.sh`, which
   reads `SYSTEM_TESTS_FORCE_EXECUTE` from the environment, so no template changes are
   needed.
