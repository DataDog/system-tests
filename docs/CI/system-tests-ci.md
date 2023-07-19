## CI Workflow: Github Actions

Our System-tests repository is fully integrated with Github Actions, which helps us build, execute and report tests results automatically.

The System-tests repository contains **one main workflow**: `ci.yml`. It is triggered in these cases:

- When a PR is created.
- When pushing a code into an existing PR.
- When a PR or Branch is merged into the main branch.
- Nightly the workflows are launched, executing the tests on the main branch.

### Workflow during a PR

By default, after some basic test/lint jobs, this pipeline build alls weblogs (67!) in their `prod` (last release of all Datadog components) and `dev` (last commit on main of all Datadog components) versions. Then it runs the DEFAULT scenario on all of them. All of this in parallel (so 134 jobs), it takes few minutes to run.

This workflow can validate any system-tests PR, as long as it modifies only the default scenario, which is the most common use case:

- If you modify only code in the `tests/` folder
- and if you modify only classes that do not have any `@scenario` decorator

If you modified anything else, a system based on [GitHub Action labels](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels#applying-labels-to-issues-and-pull-requests) is used to enable other scenarios.

### Label system

In any other case, you must add labels on your PR, to add other scenarios to be executed in your PR. Their names speaks by themselves:

- `run-parametric-scenario`
- `run-sampling-scenario`
- `run-profiling-scenario`
- `run-open-telemetry-scenarios`
- `run-libinjection-scenarios`

And if you modify something that could impact all scenarios, (or if you have any doubt), the label that run everything is `run-all-scenarios`. Be patient, the CI will take more than one hour. You can merge your PR once it has been approved, even if you have only run the tests on the default scenario.

:warning: Reviewers must pay attention on which labels should be present before approving any PR. They must add if necessary the good labels before processing the review.

When a PR is merged on the main branch, and when scheduled nightly runs are executed, all tests will always be executed on all scenarios.
