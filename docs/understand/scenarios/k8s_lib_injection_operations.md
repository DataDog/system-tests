# Kubernetes Library Injection Tests: Basic Operations

## Job Matrix Definition

The K8s Lib Injection scenarios rely on a component version matrix
(see: [Component Version Matrix Configuration](k8s_lib_injection.md#component-version-matrix-configuration)).
This matrix defines which testable component versions (e.g., injector, operator,
cluster-agent, etc.) are exercised by system-tests.

**Working process:** Updating the testable components matrix is straightforward —
just open a PR following the instructions in the
[Component Version Matrix Configuration](k8s_lib_injection.md#component-version-matrix-configuration)
documentation. That PR will have the **APM DCS DevX** team and the
**Injection Platform** team as reviewers.

## Weekly Auto-Update (GitHub Actions → Auto PR)

We automatically refresh the testable component versions once per week.
A dedicated GitHub Actions workflow opens a PR with the version bumps:

- **Workflow:**
  [update_k8s_components.yml](https://github.com/DataDog/system-tests/actions/workflows/update_k8s_components.yml)
- **Example auto-PRs:**
  - [#6314](https://github.com/DataDog/system-tests/pull/6314)
  - [#6244](https://github.com/DataDog/system-tests/pull/6244)
  - [#6180](https://github.com/DataDog/system-tests/pull/6180)

**Working process:** A PR is generated once a week (over the weekend).
The **APM DCS DevX** team reviews and merges it if no issues are found.
If any problems are detected, the **Injection Platform** team is notified so
both teams can work together to identify the root cause.

## Nightly Validation of the Combined Matrix (Scheduled CI)

In addition to the weekly bump, we run nightly jobs that validate the combined
component-version matrix to catch incompatibilities early.

- **Scheduled job name:** K8s Lib Injection Nightly
- **Schedule location (GitLab):**
  [Pipeline Schedules](https://gitlab.ddbuild.io/DataDog/system-tests/-/pipeline_schedules)

**Working process:** In case of failure, a notification is sent to the
[#injection-platform-alerts](https://dd.slack.com/archives/injection-platform-alerts)
Slack channel. The **APM DCS DevX** team and the **Injection Platform** team
work together to identify the root cause of the issue.

## Note on Tracer / Injector Repos

Tracer repositories and the injector repository typically run their own
system-tests against stable or pinned versions of dependencies/components
(instead of continuously tracking the full evolving matrix).
