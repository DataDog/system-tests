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
`dev` version uses `main` / `master` branch by default but supports target branch overrides for components that provide development artifacts.

If the PR's title includes `[target_library@branch_name_to_test]` the workflow will use `branch_name_to_test` instead of `main/master` branch. Multiple branch overrides can be specified simultaneously for different libraries:

```
My PR title [java@my-java-branch][dotnet@my-dotnet-branch][ruby@my-ruby-branch]
```

The native C binary loader accepts independent tracer and injector branch
overrides:

```shell
LIBRARY_TARGET_BRANCH=my-dd-trace-c-branch \
  AUTO_INJECT_TARGET_BRANCH=my-injector-branch \
  ./utils/scripts/load-binary.sh c
```

Without an override, each component uses its latest production package. An
explicit branch override is resolved to an immutable commit SHA and switches
only that component to its corresponding package in
`installtesting.datad0g.com`. Every selected image is verified before the weblog
is built.

Each library in the CI matrix will use its own specified branch. Libraries without an override continue to use the default branch.

As a security measure, the "Fail if target branch is specified" job always fails if a target branch is selected.

### Scenario detection in CI

When a modification is made in system tests, the CI tries to detect which scenario to run:

1. based on modified files in `tests/`, by extracting scenarios targeted by those files
2. based on any modification in a `tests/**/utils.py`, and applying the logic 1. on any sub file in `tests/**`
