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
      - uses: actions/upload-artifact@v4
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
      with:
        library: java
        binaries_artifact: binaries
        desired_execution_time: 900
        scenarios_groups: tracer-release
        skip_empty_scenarios: true
```

## Parameters

| Name                     | Description                                                                                     | Type    | Required | Default    |
| ------------------------ | ----------------------------------------------------------------------------------------------- | ------- | -------- | ---------- |
| `artifact_retention_days`   | How long should artifacts produced by the workflow should be retained                           | number  | false    | 14         |
| `binaries_artifact`         | Artifact name containing the binaries to test                                                   | string  | false    | *empty*    |
| `display_summary`           | Display a workflow summary containing owners of failed tests                                    | boolean | false    | false      |
| `desired_execution_time`    | In seconds, system-tests will try to respect this time budget.                                  | number  | false    | *empty*    |
| `excluded_scenarios`        | Comma-separated list of scenarios not to run                                                    | string  | false    | *empty*    |
| `force_execute`             | Comma-separated list of tests to run even if they are skipped by manifest or decorators         | string  | false    | *empty*    |
| `library`                   | Library to test                                                                                 | string  | true     | —          |
| `parametric_job_count`      | How many jobs should be used to run PARAMETRIC scenario                                         | number  | false    | 1          |
| `push_to_test_optimization` | Push tests results to DataDog Test Optimization. Requires TEST_OPTIMIZATION_API_KEY secrets     | boolean | false    | false      |
| `ref`                       | system-tests ref to run the tests on (can be any valid branch, tag or SHA in system-tests repo) | string  | false    | main       |
| `scenarios`                 | Comma-separated list scenarios to run                                                           | string  | false    | DEFAULT    |
| `scenarios_groups`          | Comma-separated list of scenarios groups to run                                                 | string  | false    | *empty*    |
| `skip_empty_scenarios`      | Skip scenarios that contain only xfail or irrelevant tests                                      | boolean | false    | false      |

## Secrets

For some purposes, secrets are used in the workflow:

| Name                                   | Description
| -------------------------------------- | ----------------------------------------------------------------------------------
| CIRCLECI_TOKEN                         | Only used with `_system_tests_dev_mode`
| DD_API_KEY                             | Some scenarios requires valid API and APP keys
| DD_APPLICATION_KEY                     |
| DD_API_KEY_2                           |
| DD_APP_KEY_2                           |
| DD_API_KEY_3                           |
| DD_APP_KEY_3                           |
| DOCKERHUB_USERNAME and DOCKERHUB_TOKEN | If both are set, all docker pull are authenticated, which offer higher rate limit
| TEST_OPTIMIZATION_API_KEY              | The DD_API_KEY to use to push tests runs to DataDog Test Optimization


You can sends them ,either by using `secrets: inherit` ([doc](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idsecretsinherit)), or [use explicit secret ids](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idsecretssecret_id)


## Private parameters

Those parameters are used only by system-tests own CI

| Name                                  | Description                                                          | Type    | Required | Default    |
| ------------------------------------- | ---------------------------------------------------------------------| ------- | -------- | ---------- |
| `_system_tests_dev_mode`              | Shall we run system tests in dev mode (library and agent dev binary) | boolean | false    | false      |
| `_system_tests_library_target_branch` | If system-tests dev mode, the branch to use for the library          | string  | false    |            |
| `_build_buddies_images`               | Shall we build buddies images                                        | boolean | false    | false      |
| `_build_proxy_image`                  | Shall we build proxy image                                           | boolean | false    | false      |
| `_build_lambda_proxy_image`           | Shall we build the lambda-proxy image                                | boolean | false    | false      |
| `_build_python_base_images`           | Shall we build python base images for tests on python tracer         | boolean | false    | false      |
| `_enable_replay_scenarios`            | Enable replay scenarios, should only be used in system-tests CI      | boolean | false    | false      |
