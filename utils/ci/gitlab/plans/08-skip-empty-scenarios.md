# Feature: `skip_empty_scenarios` input

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `.github/workflows/run-end-to-end.yml` line 112 — sets `SYSTEM_TESTS_SKIP_EMPTY_SCENARIO`

When `true`, scenarios whose tests are all xfail or irrelevant are skipped entirely.
The run scripts consume this via the `SYSTEM_TESTS_SKIP_EMPTY_SCENARIO` environment
variable.

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   skip_empty_scenarios:
     description: "Skip scenarios that contain only xfail or irrelevant tests"
     type: boolean
     default: false
   ```
2. Add to the `variables` block of `run_test_pipeline`:
   ```yaml
   run_test_pipeline:
     variables:
       SYSTEM_TESTS_SKIP_EMPTY_SCENARIO: "$[[ inputs.skip_empty_scenarios ]]"
     trigger:
       ...
   ```
   No template changes are needed; `./run.sh` already reads this variable.
