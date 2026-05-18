# Feature: `parametric_job_count` input

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `utils/ci/gitlab/build_pipeline.py` — generates child pipeline YAML
- `utils/ci/gitlab/system-tests.yml` — Jinja2 job template
- `utils/scripts/compute-workflow-parameters.py` — accepts `--parametric-job-count`;
  produces `params["parametric"]["job_count"]`, `params["parametric"]["job_matrix"]`,
  and `params["parametric"]["enable"]`

The `PARAMETRIC` scenario can be split across N parallel jobs to reduce wall-clock
time. In the GitHub workflow this is controlled by `parametric_job_count` (default 1).
Currently the GitLab pipeline does not generate parametric jobs at all.

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   parametric_job_count:
     description: "Number of parallel jobs for the PARAMETRIC scenario"
     type: number
     default: 1
   ```
2. In the `build_test_pipeline` script, add
   `--parametric-job-count $[[ inputs.parametric_job_count ]]` to the
   `compute-workflow-parameters.py` invocation.

### `utils/ci/gitlab/build_pipeline.py`

3. Read the parametric section from params and pass it to the template:
   ```python
   template.render(
       ...,
       parametric=params["parametric"],
   )
   ```

### `utils/ci/gitlab/system-tests.yml`

4. Add a parametric block to the template that renders one job per matrix entry when
   `parametric["enable"]` is true:
   ```yaml
   {% if parametric.enable %}
   {% for job_index in parametric.job_matrix %}
   run_{{ library }}_PARAMETRIC_{{ job_index }}:
     image: registry.ddbuild.io/ci/libdatadog-build/system-tests:100425777
     tags:
       - docker-in-docker:amd64
     stage: {{ stage }}
     variables:
       SYSTEM_TESTS_PARAMETRIC_JOB_COUNT: "{{ parametric.job_count }}"
       SYSTEM_TESTS_PARAMETRIC_JOB_INDEX: "{{ job_index }}"
     script:
       - ./build.sh {{ library }} -i runner
       - ./run.sh PARAMETRIC
     before_script:
       - ...  # same docker login as other jobs
   {% endfor %}
   {% endif %}
   ```
