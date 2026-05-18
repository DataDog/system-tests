# Feature: `push_to_test_optimization` + `test_optimization_datadog_site` inputs

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `utils/ci/gitlab/system-tests.yml` — Jinja2 job template
- `.github/actions/push_to_test_optim/action.yml` — GitHub equivalent
- `.github/workflows/run-end-to-end.yml` lines 546-550

After all run jobs complete, the GitHub workflow runs `datadog-ci junit upload` to
push `reportJunit.xml` files to Datadog Test Optimization, tagged with the service,
environment, and codeowners. It requires a `TEST_OPTIMIZATION_API_KEY` secret and an
optional `DATADOG_SITE` setting.

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   push_to_test_optimization:
     description: "Push test results to Datadog Test Optimization (requires TEST_OPTIMIZATION_API_KEY CI variable)"
     type: boolean
     default: false
   test_optimization_datadog_site:
     description: "Datadog site to use for Test Optimization"
     default: "datadoghq.com"
   ```

2. Add a new `push_test_optimization` job:
   ```yaml
   push_test_optimization:
     image: node:lts-slim
     stage: report          # new stage after `run`, see note below
     rules:
       - if: '$[[ inputs.push_to_test_optimization ]] == "true"'
     needs:
       - job: run_test_pipeline
         artifacts: true
     script:
       - npm install -g @datadog/datadog-ci
       - |
         datadog-ci junit upload logs*/reportJunit.xml \
           --service system-tests \
           --env ci \
           --xpath-tag "test.codeowners=/testcase/properties/property[@name='test.codeowners']"
     variables:
       DATADOG_SITE: "$[[ inputs.test_optimization_datadog_site ]]"
       DATADOG_API_KEY: "$TEST_OPTIMIZATION_API_KEY"
   ```

### `utils/ci/gitlab/system-tests.yml`

3. Run jobs must export their JUnit XML so the `push_test_optimization` job can
   access them. Add to the run job template:
   ```yaml
   artifacts:
     when: always
     paths:
       - logs/reportJunit.xml
   ```
   (This can be merged with the `artifacts: reports: junit` block introduced by the
   `display_summary` feature — plan `09-display-summary.md`.)

### GitLab project/group settings

4. Add `TEST_OPTIMIZATION_API_KEY` as a masked CI/CD variable in the GitLab
   project or group settings. This is the equivalent of the GitHub
   `TEST_OPTIMIZATION_API_KEY` secret.

## Notes

- The `report` stage must be declared in whatever top-level pipeline configuration
  defines the stages list, after the `run` stage.
- The GitHub action also attempts to get a short-lived API key via `dd-sts-action`
  as a fallback. This can be added later via a `before_script` that calls the
  appropriate AWS SSM parameter (consistent with the existing `before_script` pattern
  already used in the GitLab jobs).
