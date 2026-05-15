# Feature: `weblogs` input

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `utils/scripts/compute-workflow-parameters.py` — accepts `--weblogs`

Currently, no `weblogs` input exists in the GitLab pipeline, so all weblogs are always
run. The GitHub workflow exposes this as a `weblogs` input (comma-separated, default
`""`), allowing callers to restrict the run to a subset of weblogs.

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   weblogs:
     description: "Comma-separated list of weblogs to run (all weblogs if empty)"
     default: ""
   ```
2. In the `build_test_pipeline` script, add `--weblogs "$[[ inputs.weblogs ]]"` to
   the `compute-workflow-parameters.py` invocation.
