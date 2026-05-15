# Feature: `scenarios_groups` input

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `utils/scripts/compute-workflow-parameters.py` — accepts `--groups`

Currently, the `build_test_pipeline` script hardcodes `-g all`, meaning all scenario
groups are always selected. The GitHub workflow exposes this as a `scenarios_groups`
input (comma-separated, default `""`).

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   scenarios_groups:
     description: "Comma-separated list of scenario groups to run"
     default: "all"
   ```
   Default is `"all"` (not `""`) to preserve current GitLab behaviour.
2. In the `build_test_pipeline` script, replace the hardcoded `-g all` with
   `--groups "$[[ inputs.scenarios_groups ]]"`.
