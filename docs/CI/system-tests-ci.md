## CI Workflow: Github Actions

Our System-tests repository is fully integrated with Github Actions, which helps us build, execute and report tests results automatically.

The System-tests repository includes **three main build pipelines**:

* Parametric tests (parametric.yml)
* Lib-injection tests (experimental.yml)
* End-to-End Test the tests (ci.yml)

The pipeline “ci.yml“ is the **largest and most demanding workflow** that takes the longest to execute it , due to the following **reasons**:

* We are testing APM library for all languages.
* We are testing APM library over a lot of different frameworks/applications.
* This type of testing has proven to be effective and the number of test cases and the number of technologies to be tested is growing exponentially every day.

The **workflows** listed above are **triggered in these cases**:

* When a PR is created.
* When pushing a code into an existing PR.
* When a PR or Branch is merged into the main branch.
* Nightly the workflows are launched, executing the tests on the main branch.

**In order to reduce test execution times, reduce the number of resources used (Github runners) and speed up or make the work of test developers more flexible, we have implemented:**

* A labeling system capable of reducing the number of test scenarios to be run for a PR.
* A build system based on the code paths you modify in a PR

### Label system

The labeling system only applies to the PR.  This system is based on [GitHub Action labels](https://docs.github.com/en/issues/using-labels-and-milestones-to-track-work/managing-labels#applying-labels-to-issues-and-pull-requests).

By default, when you create a PR on system-tests, ci.yml tests will only be launched on the default scenario.

If you want to run all scenarios, you must add the label `run-all-scenarios`

Then you can also re-run the tests on the default scenario by simply removing the label again.

You can merge your PR once it has been approved, even if you have only run the tests on the default scenario. A reviewer can run tests on all scenarios, if necessary, by adding the "run-all-scenarios" label. 

When a PR is merged on the main branch, and when scheduled nightly runs are executed, all tests will always be executed on all scenarios.
