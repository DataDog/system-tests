## CI Workflow: Github Actions

Our System-tests repository uses GitHub Actions to build, execute, and report most test results automatically. Native C end-to-end coverage runs in GitLab CI on DinD runners.

The System-tests repository contains **one main workflow**: `ci.yml`. It is triggered in these cases:

- When a PR is created.
- When pushing a code into an existing PR.
- When a PR or Branch is merged into the main branch.
- Nightly the workflows are launched, executing the tests on the main branch.

### Workflow during a PR

By default, after some basic test/lint jobs, this pipeline build alls weblogs (67!) in their `prod` (last release of all Datadog components) and `dev` (last commit on main of all Datadog components) versions. Then it runs a set of scenarios, based on which files you've modified, on all weblogs. All of this in parallel (so lot of jobs), it can take few dozain of minutes to run.

### Target branch selection
`dev` version uses `main` / `master` branch by default but, in the case of some libraries (cpp, agent, nodejs, python, ruby, and dotnet), it is possible to configure the CI to use a target branch.

If the PR's title includes `[target_library@branch_name_to_test]` the workflow will use `branch_name_to_test` instead of `main/master` branch. Multiple branch overrides can be specified simultaneously for different libraries:

```
My PR title [java@my-java-branch][dotnet@my-dotnet-branch][ruby@my-ruby-branch]
```

Each library in the CI matrix will use its own specified branch. Libraries without an override continue to use the default branch.

As a security measure, the "Fail if target branch is specified" job always fails if a target branch is selected.

### Scenario detection in CI

When a modification is made in system tests, the CI tries to detect which scenario to run:

1. based on modified files in `tests/`, by extracting scenarios targeted by those files
2. based on any modification in a `tests/**/utils.py`, and applying the logic 1. on any sub file in `tests/**`


## CI Workflow: GitLab end-to-end pipeline

The GitLab end-to-end pipeline (the `system_tests_param` job of `.gitlab-ci.yml`, then the [`utils/ci/gitlab/main.yml`](../../utils/ci/gitlab/main.yml) component) generates its child pipelines with `utils/ci/gitlab/build_pipeline.py`. By default, it tests the `prod` version of all components, or the binaries of upstream jobs given by `binaries_artifacts` (`custom`).

### Dev mode

Like the `dev` version of the GitHub workflow, the dev mode tests the last commit of the main branch of the agent and of the libraries. It is opt-in only: nothing runs it automatically. To use it, set these variables, either as pipeline variables (e.g. when running a pipeline from the GitLab UI), or by exporting them in the `before_script` of the `system_tests_param` job (checked by `utils/ci/gitlab/validate_param_env.py`, like the other variables of this job):

| Variable                             | Value                                                                                       |
| ------------------------------------ | ------------------------------------------------------------------------------------------- |
| `SYSTEM_TESTS_E2E_DEV_MODE`          | `true`                                                                                      |
| `SYSTEM_TESTS_E2E_TARGET_BRANCH_MAP` | Optional. JSON object `{library or "agent": branch}`, e.g. `{"python": "my-branch", "agent": "my-name-my-branch-py3"}`, to use these branches instead of main/master (see [target branch selection](#target-branch-selection) for the libraries supporting it). Branches of libraries that are not run are ignored. The `agent` value is not a branch but a tag of the `datadog/agent-dev` image (`master-py3` by default): the slug of the branch with a flavor suffix, e.g. `my-name-my-branch-py3` for the branch `my.name/my-branch` |

On a pipeline of another branch than main run from the GitLab UI (or the API), no library is selected by default: also set `LIBRARIES` (e.g. `python`), and `SCENARIOS` or `SCENARIO_GROUPS` to choose the scenarios (as pipeline variables, they take precedence over the ones computed from the changes of the branch).

The variable is not `SYSTEM_TESTS_DEV_MODE`: as a pipeline variable, it would also reach the jobs of the parent pipeline that run pytest. The generated jobs get `SYSTEM_TESTS_DEV_MODE=true` (manifest check of `conftest.py`) and `SYSTEM_TESTS_REPORT_ENVIRONMENT=dev`.

In dev mode, each library gets a `system_tests_dev_binaries_<library>` job, which runs `utils/scripts/load-binary.sh` for the agent and for the library (`utils/ci/gitlab/jobs/load_dev_binaries.py`). The build, run and parametric jobs of the library download its artifacts, like they download the binaries of upstream jobs. Each `load-binary.sh` call is killed after 10 minutes and retried, its curl calls have a connection and transfer timeout, and its git clones are aborted if they stall.

The dev agent image (`datadog/agent-dev`) is not in the image mirror: the run jobs pull it from Docker Hub. The mirror can't mirror it yet, as it pins each image to the digest it had when it was added to `mirror_images.lock.yaml`, while `datadog/agent-dev:master-py3` changes with every commit of the agent.

The dev mode is rejected (the pipeline generation fails):

* with `binaries_artifacts` or `binaries_artifact_path`: both give the binaries to test
* for libraries that need GitHub credentials the GitLab jobs don't have yet: `cpp_httpd`, `cpp_nginx`, `python_lambda` and `nodejs_lambda` (artifacts of GitHub workflows of other repositories), and the `c` and `auto_inject` target branches (internal repositories)
* for libraries without a dev version: `java_otel`, `nodejs_otel`, `python_otel` and `otel_collector`

For `golang`, `load-binary.sh` calls the GitHub API: the job gets a read-only GitHub token from `dd-octo-sts` (`gitlab.github-access.read` policy, only available to pipelines of DataDog/system-tests), and calls it unauthenticated if it can't get one.
