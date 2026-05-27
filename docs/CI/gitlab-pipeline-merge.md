# Merging the new end-to-end GitLab pipeline with the SSI pipeline

## Context

There are currently two separate GitLab CI pipelines for system-tests:

- **SSI pipeline** — the existing `.gitlab-ci.yml` on `main`, used by all tracer repos via
  `one-pipeline` (`libdatadog-build/templates/one-pipeline.yml`)
- **End-to-end prototype** — the new `utils/ci/gitlab/main.yml` on this branch, designed to
  replace the GitHub Actions end-to-end workflow

The goal is to merge them into a single, unified GitLab pipeline.

---

## How the SSI pipeline currently works

### Distribution chain

```
libdatadog-build/templates/one-pipeline.yml
  └── includes (remote): gitlab-templates.ddbuild.io/libdatadog/include/single-step-instrumentation-tests.yml
        (base job templates: .base_job_onboarding, .base_job_k8s_docker_ssi)

each tracer repo (.gitlab-ci.yml)
  └── includes: .gitlab/one-pipeline.locked.yml
        └── includes (remote, content-addressed): gitlab-templates.ddbuild.io/libdatadog/one-pipeline/ca/<hash>/one-pipeline.yml
              └── defines: configure_system_tests + system_tests jobs
```

### configure_system_tests → system_tests flow

`configure_system_tests` in `one-pipeline.yml`:
1. Pulls system-tests at `$SYSTEM_TESTS_REF` (default: `main`)
2. Builds the runner
3. Calls `utils/scripts/ci_orchestrators/external_gitlab_pipeline.py`, which **reads
   `.gitlab-ci.yml` directly** from the cloned system-tests repo, injects SSI image
   variables (`K8S_LIB_INIT_IMG`, `DD_INSTALLER_LIBRARY_VERSION`, etc.), filters by
   `$SYSTEM_TESTS_LIBRARY`, and dumps the result as `system_tests_pipeline.yml`
4. `system_tests` triggers `system_tests_pipeline.yml` as a child pipeline

The system-tests `.gitlab-ci.yml` is therefore **already the source of truth** for what
runs in each tracer repo's SSI pipeline. `one-pipeline` just reads and filters it.

### gitlab-templates.ddbuild.io is an S3 bucket

Templates are served from `s3://gitlab-templates.ddbuild.io`. There are two publishing paths:

| Path | URL pattern | When published |
|---|---|---|
| Content-addressed (immutable) | `libdatadog/one-pipeline/ca/<hash>/` | Automatically on every libdatadog-build pipeline |
| Mutable "latest stable" | `libdatadog/include/` | Manually via `publish-templates-to-versionless-bucket` job |

Any repo with S3 write access to that bucket can publish its own templates there. The
mutable path is what `one-pipeline.yml` uses to include `single-step-instrumentation-tests.yml`.

---

## Why the SSI pipeline is complex

There are three scenario categories in the SSI pipeline:

| Category | Scenarios | Infrastructure | Complexity |
|---|---|---|---|
| `aws_ssi` | `simple_onboarding`, `*_profiling`, `*_appsec` | Real EC2 VMs via Pulumi | High |
| `dockerssi` | `DOCKER_SSI` | Docker-in-Docker | Low (same as e2e) |
| `libinjection` | `K8S_LIB_INJECTION_*` | kind clusters | Moderate |

**All the complexity in `.gitlab-ci.yml` comes from `aws_ssi` alone:**

- **Sequential per-language stages** (`nodejs → java → dotnet → ...`) — AWS EC2 and subnet
  quotas prevent running all languages in parallel
- **Staggered `.delayed_base_job`** on releases — avoids exhausting AWS capacity at once
- **Pulumi credentials, SSH keys, keypairs** in `before_script` — required for EC2 provisioning
- **`delete_amis`, `delete_ec2_instances` scheduled jobs** — AWS resource cleanup
- **`check_merge_labels`, image build jobs** — infra maintenance

`DOCKER_SSI` and `K8S_LIB_INJECTION_*` run on the same `docker-in-docker:amd64` runners as
end-to-end tests and have **none** of these constraints.

---

## The new end-to-end prototype

`utils/ci/gitlab/main.yml` is a GitLab CI component (`spec: inputs:`) with two jobs:

1. **`build_test_pipeline`** — for each library: runs
   `compute-workflow-parameters.py --format json`, pipes through `build_pipeline.py`
   (Jinja2) → writes `generated-pipeline-${library}.yml` (one file per library)
2. **`run_test_pipeline_{library}`** — one trigger job per known library, each triggering
   its own `generated-pipeline-${library}.yml` as a child pipeline; gated by a rule that
   checks whether the library appears in `inputs.libraries`

`utils/ci/gitlab/system-tests.yml` is the Jinja2 template that produces one flat job per
`(scenario, weblog_variant)` pair:

```
run_{library}_{scenario}_{variant}
```

The component exposes two inputs: `stage` (for the generated jobs) and `libraries`.
It currently hardcodes `-g all` with a fixed exclusion list and assumes it runs from within
the system-tests repo directory.

---

## Proposed merge strategy

### Core insight

`DOCKER_SSI` and `K8S_LIB_INJECTION_*` are structurally identical to end-to-end scenarios:
they run in Docker/K8s on standard CI runners. They can be expressed in the same Jinja2
template with no special infrastructure. Only `aws_ssi` scenarios need to remain separate.

### Step 1 — Split the SSI pipeline by infrastructure type

Separate `.gitlab-ci.yml` into two independent pipelines:

- **`utils/ci/gitlab/main.yml`** (this file, extended) — handles `endtoend` + `dockerssi` +
  `libinjection`. All Docker/K8s, all parallel, no AWS dependencies.
- **`utils/ci/gitlab/aws-ssi.yml`** (new) — handles `aws_ssi` only. Keeps sequential
  language stages, Pulumi infra, delayed starts, and cleanup jobs. This pipeline stays
  complex because the infrastructure requires it.

### Step 2 — Extend main.yml inputs

Add the inputs needed for one-pipeline to drive it:

```yaml
spec:
  inputs:
    stage:
    build_stage:
      default: "build"          # stage for build_test_pipeline itself
    run_stage:
      default: "run"            # stage for run_test_pipeline_{library} jobs
    libraries:
      default: "java python nodejs"
    scenarios_groups:
      default: "all"            # replaces hardcoded "-g all"
    excluded_scenarios:
      default: "APM_TRACING_E2E_OTEL,..."
```

The `build_stage` and `run_stage` inputs allow one-pipeline to map both jobs onto its
single `shared-pipeline` stage.

### Step 3 — Extend the Jinja2 template for SSI variables

`system-tests.yml` needs to forward the SSI image variables into generated jobs so that
tracer repos can inject `K8S_LIB_INIT_IMG`, `DD_INSTALLER_LIBRARY_VERSION`, etc.:

```jinja
run_{{library}}_{{scenario}}_{{variant}}:
  variables:
    WEBLOG_VARIANT: {{variant}}
    {% if ssi_library_version is defined %}
    DD_INSTALLER_LIBRARY_VERSION: "{{ssi_library_version}}"
    {% endif %}
    {% if k8s_lib_init_img is defined %}
    K8S_LIB_INIT_IMG: "{{k8s_lib_init_img}}"
    {% endif %}
```

These values flow from `build_test_pipeline`'s environment into the template at generation
time, so the child pipeline jobs carry them as static variables.

### Step 4 — Update configure_system_tests in one-pipeline

Replace the `external_gitlab_pipeline.py` call with the new generation approach:

```yaml
configure_system_tests:
  script:
    - *verify-variables
    - cd /system-tests
    - git pull && git checkout $SYSTEM_TESTS_REF
    - ./build.sh -i runner
    - source venv/bin/activate && pip install Jinja2
    - |
      python utils/scripts/compute-workflow-parameters.py "$SYSTEM_TESTS_LIBRARY" \
        -g "$SYSTEM_TESTS_SCENARIOS_GROUPS" \
        --format json \
        --output params.json
    - |
      python utils/ci/gitlab/build_pipeline.py \
        --stage test \
        --library "$SYSTEM_TESTS_LIBRARY" \
        --params params.json \
        --ssi-library-version "pipeline-${CI_PIPELINE_ID}" \
        --k8s-lib-init-img "${APM_ECOSYSTEMS_ECR_BASE}/${LIB_INJECTION_NAME}:glci${CI_PIPELINE_ID}" \
        > system_tests_pipeline.yml
    - cp system_tests_pipeline.yml $CI_PROJECT_DIR
```

This removes `ALLOW_MULTIPLE_CHILD_LEVELS`, `external_gitlab_pipeline.py`, and the
`--format gitlab` code path entirely.

### Step 5 — Publish main.yml to S3 (optional, for direct include)

If one-pipeline should include `main.yml` without cloning system-tests, system-tests CI can
push it to the S3 bucket on merge to main:

```yaml
publish-gitlab-component:
  stage: publish
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  script:
    - aws s3 cp utils/ci/gitlab/main.yml s3://gitlab-templates.ddbuild.io/system-tests/include/main.yml
    - aws s3 cp utils/ci/gitlab/system-tests.yml s3://gitlab-templates.ddbuild.io/system-tests/include/system-tests.yml
    - aws s3 cp utils/ci/gitlab/build_pipeline.py s3://gitlab-templates.ddbuild.io/system-tests/include/build_pipeline.py
```

One-pipeline would then include it via:

```yaml
include:
  - remote: https://gitlab-templates.ddbuild.io/system-tests/include/main.yml
```

This makes system-tests the owner of its own pipeline distribution, with no git checkout
needed inside `configure_system_tests`.

---

## What stays, what goes

| Current artifact | Fate |
|---|---|
| `.gitlab-ci.yml` (all languages, all scenario types) | Split: Docker/K8s → `main.yml`; AWS → `aws-ssi.yml` |
| `external_gitlab_pipeline.py` | Deleted — replaced by `build_pipeline.py` + Jinja2 |
| `ALLOW_MULTIPLE_CHILD_LEVELS` variable | Deleted — single code path |
| `compute-workflow-parameters.py --format gitlab` | Deleted — `--format json` + Jinja2 only |
| Sequential language stages in `.gitlab-ci.yml` | Kept in `aws-ssi.yml` only |
| `.delayed_base_job`, delete_amis, delete_ec2_instances | Kept in `aws-ssi.yml` only |
| `single-step-instrumentation-tests.yml` base job templates | Kept in `libdatadog-build`, referenced by `aws-ssi.yml` |

---

## Constraints and caveats

- **`include: ref:` cannot use CI variables** — GitLab does not expand `$SYSTEM_TESTS_REF`
  in `include: project: ref:`. The S3 publish approach (Step 5) sidesteps this entirely since
  `remote:` URLs are fetched at pipeline creation using whatever is currently in S3.
- **S3 write access** — system-tests CI needs credentials to write to
  `s3://gitlab-templates.ddbuild.io`. This requires coordination with the libdatadog-build
  team to grant access or to establish a separate bucket path.
- **`aws_ssi` pipeline is out of scope** — its complexity is infrastructure-driven and cannot
  be simplified without changing the underlying AWS/Pulumi approach.
