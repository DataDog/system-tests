# Feature: `excluded_scenarios` input

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `utils/scripts/compute-workflow-parameters.py` — accepts `--excluded-scenarios`

Currently, the `build_test_pipeline` script hardcodes the following exclusion list
inline in a shell variable:

```
APM_TRACING_E2E_OTEL,APM_TRACING_E2E_SINGLE_SPAN,OTEL_TRACING_E2E,OTEL_METRIC_E2E,OTEL_LOG_E2E,INTEGRATION_FRAMEWORKS
```

The GitHub workflow exposes this as an `excluded_scenarios` input (comma-separated,
default `""`).

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   excluded_scenarios:
     description: "Comma-separated list of scenarios not to run"
     default: "APM_TRACING_E2E_OTEL,APM_TRACING_E2E_SINGLE_SPAN,OTEL_TRACING_E2E,OTEL_METRIC_E2E,OTEL_LOG_E2E,INTEGRATION_FRAMEWORKS"
   ```
   The default preserves the list currently hardcoded in the script.
2. In the `build_test_pipeline` script, remove the hardcoded `EXCLUDED_SCENARIOS`
   shell variable and replace `--excluded-scenarios $EXCLUDED_SCENARIOS` with
   `--excluded-scenarios "$[[ inputs.excluded_scenarios ]]"`.
