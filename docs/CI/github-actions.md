system-tests expose an official reusable workflow that allow to create a simple workflow running system-tests


```yaml
name: System Tests

on:
  pushes:
    branches:
      - main
  pull_request:
    branches:
      - "**"

jobs:
  # first, build the artifact to be tested. This part is related to your repo
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./build.sh
      - uses: actions/upload-artifact@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f # v7.0.0
        with:
          name: binaries
          path: path/to/your/binary


  system-tests:
    needs:
      - build
    uses:  DataDog/system-tests/.github/workflows/system-tests.yml@main
      secrets: inherit
      permissions:
        contents: read
        id-token: write
      with:
        library: java
        binaries_artifact: binaries
        desired_execution_time: 900
        scenarios_groups: tracer-release
        skip_empty_scenarios: true
```

## Parameters

| Name                             | Description                                                                                     | Type    | Required | Default       |
| -------------------------------- | ----------------------------------------------------------------------------------------------- | ------- | -------- | ------------- |
| `artifact_retention_days`        | How long should artifacts produced by the workflow should be retained                           | number  | false    | 14            |
| `binaries_artifact`              | Artifact name containing the binaries to test                                                   | string  | false    | *empty*       |
| `desired_execution_time`         | In seconds, system-tests will try to respect this time budget.                                  | number  | false    | *empty*       |
| `excluded_scenarios`             | Comma-separated list of scenarios not to run                                                    | string  | false    | *empty*       |
| `force_execute`                  | Comma-separated list of tests to run even if they are skipped by manifest or decorators         | string  | false    | *empty*       |
| `library`                        | Library to test                                                                                 | string  | true     | —             |
| `parametric_job_count`           | How many jobs should be used to run PARAMETRIC scenario                                         | number  | false    | 1             |
| `_experimental_parametric_runs_on` | JSON-encoded runner label, label array, or runner group definition for PARAMETRIC              | string  | false    | `{"group":"APM Larger Runners"}` |
| `push_to_test_optimization`      | Push tests results to DataDog Test Optimization. Fetches credentials automatically via Datadog Workload Identity Federation | boolean | false    | false         |
| `test_optimization_datadog_site` | DataDog site to use for test optimization                                                       | string  | false    | datadoghq.com |
| `ref`                            | system-tests ref to run the tests on (can be any valid branch, tag or SHA in system-tests repo) | string  | false    | main          |
| `scenarios`                      | Comma-separated list scenarios to run                                                           | string  | false    | DEFAULT       |
| `scenarios_groups`               | Comma-separated list of scenarios groups to run                                                 | string  | false    | *empty*       |
| `skip_empty_scenarios`           | Skip scenarios that contain only xfail or irrelevant tests                                      | boolean | false    | false         |


Note: the calling repo must be allowed by the `system-tests` Datadog Workload Identity Federation [intake mappings](https://app.datadoghq.com/organization-settings/workload-identity-federation/intake-mappings). Otherwise, jobs are not tagged with `ci.framework.name:system-tests`, and results are not pushed to Test Optimization even if `push_to_test_optimization` is `true` (both are best effort, and never fail the job). Ask in [#apm-shared-testing](https://dd.enterprise.slack.com/archives/C025TJ4RZ8X) to be added.

### Parametric runners and parallelism

To run parametric tests on standard GitHub-hosted runners, pass a JSON-encoded
runner label:

```yaml
with:
  _experimental_parametric_runs_on: '"ubuntu-24.04"'
  parametric_job_count: 32
```

`parametric_job_count` controls the number of shards. Within each Ruby parametric
job, pytest automatically chooses its worker count from the runner's CPU count.
When moving to smaller runners, increase the shard count to compensate for fewer
workers per job, then tune it using CI timings. Each shard builds its own test
image, so additional shards also add build overhead.

`desired_execution_time` controls end-to-end sharding; it does not size parametric
shards or set a job timeout.

## Permissions

The following permissions are always required:

| Permission       | Reason                                                      |
| ---------------- | ----------------------------------------------------------- |
| `contents: read` | Checkout the repository                                     |
| `id-token: write` | Required by downstream workflows to fetch Datadog credentials via Datadog Workload Identity Federation. GitHub validates this upfront, so it must be granted even if test optimization is disabled |

## Secrets

For some purposes, secrets are used in the workflow:

| Name                                   | Description
| -------------------------------------- | ----------------------------------------------------------------------------------
| DOCKERHUB_USERNAME and DOCKERHUB_TOKEN | If both are set, all docker pull are authenticated, which offer higher rate limit
| DD_API_KEY, DD_APPLICATION_KEY, DD_API_KEY_2, DD_APP_KEY_2, DD_API_KEY_3, DD_APP_KEY_3 | Not used anymore: scenarios send their data to a mocked backend. Still accepted, so that existing callers don't break

Secrets never reach the test runner: it fails if it finds one in its environment (see
[troubleshooting](../execute/troubleshooting.md#environment-variables-look-like-secrets)).


You can sends them ,either by using `secrets: inherit` ([doc](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idsecretsinherit)), or [use explicit secret ids](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idsecretssecret_id)

## Running system-tests in your own workflow

If you don't use the reusable workflow, add the [`disable_containerd_image_store`](../../.github/actions/disable_containerd_image_store/action.yml) action to every job that runs system-tests, before the job pulls, builds or loads any docker image:

```yaml
- name: Disable the containerd image store
  uses: DataDog/system-tests/.github/actions/disable_containerd_image_store@main
```

On runners using the containerd image store (the default from Docker 29, e.g. `ubuntu-26.04`), the first container of a job can take more than 60s to be created, and the scenario fails with `Container proxy can't be started`.


## Private parameters

Those parameters are used only by system-tests own CI

| Name                                  | Description                                                          | Type    | Required | Default    |
| ------------------------------------- | ---------------------------------------------------------------------| ------- | -------- | ---------- |
| `_system_tests_dev_mode`              | Shall we run system tests in dev mode (library and agent dev binary) | boolean | false    | false      |
| `_system_tests_library_target_branch_map` | If system-tests dev mode, JSON map of library to branch (e.g. `{"java":"b1","dotnet":"b2"}`) | string  | false    |            |
| `_build_buddies_images`               | Shall we build buddies images                                        | boolean | false    | false      |
| `_build_proxy_image`                  | Shall we build proxy image                                           | boolean | false    | false      |
| `_build_lambda_proxy_image`           | Shall we build the lambda-proxy image                                | boolean | false    | false      |
| `_enable_replay_scenarios`            | Enable replay scenarios, should only be used in system-tests CI      | boolean | false    | false      |
