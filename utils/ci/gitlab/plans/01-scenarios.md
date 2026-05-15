# Feature: `scenarios` input

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `utils/scripts/compute-workflow-parameters.py` — accepts `--scenarios`

Currently, no `scenarios` input exists in the GitLab pipeline. The set of scenarios
to run is determined entirely by `scenarios_groups` and `excluded_scenarios`.

In the GitHub workflow (`system-tests.yml` input `scenarios`), a caller can pass a
comma-separated list of scenario names to run directly, bypassing group-based
selection. Default is `DEFAULT`.

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   scenarios:
     description: "Comma-separated list of scenarios to run"
     default: ""
   ```
2. In the `build_test_pipeline` script, add `--scenarios "$[[ inputs.scenarios ]]"` to
   the `compute-workflow-parameters.py` invocation.
