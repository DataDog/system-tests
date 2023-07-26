## CI Workflow: Github Actions

Our System-tests repository is fully integrated with Github Actions, which helps us build, execute and report tests results automatically.

The System-tests repository contains **one main workflow**: `ci.yml`. It is triggered in these cases:

- When a PR is created.
- When pushing a code into an existing PR.
- When a PR or Branch is merged into the main branch.
- Nightly the workflows are launched, executing the tests on the main branch.

### Workflow during a PR

By default, after some basic test/lint jobs, this pipeline build alls weblogs (67!) in their `prod` (last release of all Datadog components) and `dev` (last commit on main of all Datadog components) versions. Then it runs the DEFAULT scenario on all of them. All of this in parallel (so 134 jobs), it takes few minutes to run.

This workflow can validate any system-tests PR, as long as it modifies only the default scenario, which is the most common use case. See more details in the [docs about labels](./labels)
