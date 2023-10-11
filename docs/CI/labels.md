By default, on system-tests own CI, only the default scenario is ran. It is a valid setup if:

- you modify only code in the `tests/` folder
- and if you modify only classes that do not have any `@scenario` decorator

In any other case, you'll need to add [labels](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels#applying-labels-to-issues-and-pull-requests) to add other scenarios in the CI workflow. Their names speaks by themselves:

- `run-all-scenarios`
- `run-parametric-scenario`
- `run-sampling-scenario`
- `run-profiling-scenario`
- `run-open-telemetry-scenarios`
- `run-libinjection-scenarios`
- `run-debugger-scenarios`
- `run-appsec-scenarios`

And if you modify something that could impact all scenarios, (or if you have any doubt), the label that run everything is `run-all-scenarios`. Be patient, the CI will take more than one hour. You can merge your PR once it has been approved, even if you have only run the tests on the default scenario.

:warning: Reviewers must pay attention on which labels should be present before approving any PR. They must add if necessary the good labels before processing the review.

When a PR is merged on the main branch, and when scheduled nightly runs are executed, all tests will always be executed on all scenarios.
