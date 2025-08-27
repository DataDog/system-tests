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

| Name                                  | Description                                                                                     | Type    | Required | Default    |
| ------------------------------------- | ----------------------------------------------------------------------------------------------- | ------- | -------- | ---------- |
| `binaries_artifact`                   | Artifact name containing the binaries to test                                                   | string  | false    |            |
| `build_buddies_images`                | Shall we build buddies images                                                                   | boolean | false    | false      |
| `build_proxy_image`                   | Shall we build proxy image                                                                      | boolean | false    | false      |
| `build_python_base_images`            | Shall we build python base images for tests on python tracer                                    | boolean | false    | false      |
| `build_lib_injection_app_images`      | Shall we build and push k8s lib injection weblog images                                         | boolean | false    | false      |
| `desired_execution_time`              | In seconds, system-tests will try to respect this time budget.                                  | number  | false    |            |
| `enable_replay_scenarios`             | Enable replay scenarios, should only be used in system-tests CI                                 | boolean | false    | false      |
| `excluded_scenarios`                  | Comma-separated list of scenarios not to run                                                    | string  | false    |            |
| `library`                             | Library to test                                                                                 | string  | true     | —          |
| `parametric_job_count`                | How many jobs should be used to run PARAMETRIC scenario                                         | number  | false    | 1          |
| `ref`                                 | system-tests ref to run the tests on (can be any valid branch, tag or SHA in system-tests repo) | string  | false    | main       |
| `scenarios`                           | Comma-separated list scenarios to run                                                           | string  | false    | DEFAULT    |
| `scenarios_groups`                    | Comma-separated list of scenarios groups to run                                                 | string  | false    |            |
| `skip_empty_scenarios`                | Skip scenarios that contain only xfail or irrelevant tests                                      | boolean | false    | false      |
| `force_execute`                       | Comma-separated list of tests to run even if they are skipped by manifest or decorators         | string  | false    |            |
| `display_summary`                     | Display a workflow summary containing owners of failed tests                                    | boolean | false    | false      |

## Private parameters

Those parameters are used only by system-tests own CI

| Name                                  | Description                                                                                     | Type    | Required | Default    |
| ------------------------------------- | ----------------------------------------------------------------------------------------------- | ------- | -------- | ---------- |
| `_system_tests_dev_mode`              | Shall we run system tests in dev mode (library and agent dev binary)                            | boolean | false    | false      |
| `_system_tests_library_target_branch` | If system-tests dev mode, the branch to use for the library                                     | string  | false    |            |
