# Feature: `binaries_artifact` input

## Context

Reference files:
- `utils/ci/gitlab/main.yml` — GitLab entry point
- `utils/ci/gitlab/build_pipeline.py` — generates child pipeline YAML
- `utils/ci/gitlab/system-tests.yml` — Jinja2 job template
- `utils/scripts/compute-workflow-parameters.py` — accepts `--explicit-binaries-artifact`

When a caller provides pre-built binaries (e.g. a tracer under test), they upload them
as a named CI artifact and pass the name via `binaries_artifact`. The parameter
computation script records the artifact name in `params["miscs"]["binaries_artifact"]`
and sets `ci_environment` to `"custom"`. Downstream build/run jobs must then download
that artifact before executing.

Currently this is not wired up in the GitLab pipeline.

## Changes

### `utils/ci/gitlab/main.yml`

1. Add to `spec.inputs`:
   ```yaml
   binaries_artifact:
     description: "Artifact name containing the binaries to test"
     default: ""
   ```
2. In the `build_test_pipeline` script, add
   `--explicit-binaries-artifact "$[[ inputs.binaries_artifact ]]"` to the
   `compute-workflow-parameters.py` invocation.

### `utils/ci/gitlab/build_pipeline.py`

3. Pass `binaries_artifact` (from `params["miscs"]["binaries_artifact"]`) to the
   Jinja template:
   ```python
   template.render(
       ...,
       binaries_artifact=params["miscs"]["binaries_artifact"],
   )
   ```

### `utils/ci/gitlab/system-tests.yml`

4. In the build job, add a conditional step to download the artifact when
   `binaries_artifact` is non-empty:
   ```yaml
   {% if binaries_artifact %}
   - >
     curl --fail -o binaries.zip
     "${CI_API_V4_URL}/projects/.../jobs/artifacts/..."
     # or use GitLab's `needs: [job: ..., artifacts: true]` if the artifact
     # comes from an upstream job in the same pipeline
   {% endif %}
   ```
   The exact mechanism depends on whether the artifact is produced by a job in the
   same pipeline (use `needs: artifacts: true`) or uploaded externally (use the
   GitLab artifacts API or a pre-populated `binaries/` directory via a pipeline
   variable pointing to a download URL).
