## 1. Manifests Over Decorators

If a PR adds `@missing_feature`, `@bug`, `@irrelevant`, or `@flaky` decorators whose condition depends **only** on library name, library version, or weblog variant, flag it: the manifest file should be used instead.

- Ref: [manifest.md](mdc:docs/edit/manifest.md), [skip-tests.md](mdc:docs/edit/skip-tests.md)

## 3. Manifest Version Prefix

Versions in manifest files must use the `v` prefix for "this version and above" semantics (e.g., `v1.2.0`). A bare `1.2.0` means **exactly** that version only. Flag bare versions and ask if `v` prefix was intended.

- Ref: [manifest.md](mdc:docs/edit/manifest.md)

## 8. Removed or Skipped Tests Need Manifest Entries

When a test is removed or permanently skipped for a language, add an `irrelevant` entry in the corresponding manifest file. Otherwise, downstream processes (easy-win) will incorrectly assume the test passes.

- Ref: [manifest.md](mdc:docs/edit/manifest.md)

## 11. Manifest YAML Syntax

- `bug` and `flaky` markers must include a JIRA ticket (e.g., `bug (JIRA-123)`)
- Values with special YAML characters (`>`, `<`, `:`, `#`) must be quoted
- Entries should be sorted alphabetically within each manifest file

## 11. Deactivating scenarios in weblog_metadata files

Deactivating scenarios in weblog_metadata files is rare and should only be done when it aims at deactivating a test or group of tests that runs on multiple scenarios for only one scenario.

ID: claude-07

Title: Match each manifest marker to its cause.

Rule: Pick the marker that matches the cause, as https://github.com/DataDog/system-tests/blob/main/docs/edit/skip-tests.md#declaration-decorators defines. When one PR excludes tests for different causes, give each exclusion its own reason, and make each reason state the real cause. By default, markers other than `irrelevant` and `flaky` become a non-strict xfail, and `conftest.py` also records a fixture error as `xfailed`. When a marked test fails before its assertions, the reason must name that failure.

Why: The marker tells who must act: the library team, the weblog owner, or nobody. A wrong marker or reason hides the real gap. A marker that absorbs a setup crash hides a broken test in every run.

Detect: A marker contradicts its cause, or several exclusions with different causes share one vague reason. A marked test fails during setup because of invalid configuration or a missing required secret that the marker does not describe.

Example: Bad: `missing_feature` for an endpoint that the weblog does not implement. Good: `incomplete_test_app (weblog has no /ffe endpoint)`. Bad: a marked test sets `DD_TRACE_AGENT_PORT` to the literal `agent.port`, so the library exits at startup and the run reports an expected failure.

Evidence:

• https://github.com/DataDog/system-tests/pull/8128#discussion_r4386784944
• https://github.com/DataDog/system-tests/pull/8001#discussion_r4231922375
• https://github.com/DataDog/system-tests/pull/8080
• https://github.com/DataDog/system-tests/pull/7361#discussion_r3644676643
• https://github.com/DataDog/system-tests/pull/7451
• https://github.com/DataDog/system-tests/pull/7457
• https://github.com/DataDog/system-tests/pull/7257

ID: cursor-08

Title: Do not let a minimum dev version match an older release candidate.

Rule: Do not declare a minimum dev version, such as `v4.15.0-dev`, when a release candidate (RC) of that version lacks the feature. Use the exact version without the `v` prefix until a release contains the feature. Then switch back to a minimum version. See https://github.com/DataDog/system-tests/blob/main/docs/edit/manifest.md#simple-version.

Why: Version ordering puts `4.15.0-rc1` after `4.15.0-dev`, but the RC was cut before the feature landed. The test then runs on that RC and fails.

Detect: A manifest declares a minimum dev version, and an RC of that version predates the change. A bare dev version is intentional in that case, so do not ask for the `v` prefix.

Example: Bad: `Test_Foo: v4.15.0-dev` while `4.15.0-rc1` lacks the feature. Good: `Test_Foo: 4.15.0-dev` until a release that contains the feature, such as `4.15.0`, then `Test_Foo: v4.15.0`.

Evidence: https://github.com/DataDog/system-tests/pull/7455#discussion_r3825803727

ID: claude-06

Title: Do not hide a documented feature behind NOT_REPORTED_ID.

Rule: Follow https://github.com/DataDog/system-tests/blob/main/docs/edit/features.md#hello-world-test to create each feature. A feature whose docstring links a Feature Parity Dashboard entry must pass that id as `feature_id`, not `NOT_REPORTED_ID`.

Why: The results of that feature never reach the dashboard. The current self-test skips features that use `NOT_REPORTED_ID`, so it misses this case.

Detect: A feature in `utils/_features.py` links `feature-parity.us1.prod.dog/#/?feature=<n>` and passes `feature_id=NOT_REPORTED_ID`.

Example: Bad: the docstring links `?feature=544` and the code passes `feature_id=NOT_REPORTED_ID`. Good: the code passes `feature_id=544`.

Evidence:

• https://github.com/DataDog/system-tests/pull/7820#discussion_r4159241802
• https://github.com/DataDog/system-tests/pull/6339

ID: claude-02

Title: Make a new scenario reachable by CI.

Rule: A PR that adds an end-to-end scenario must add its `Run <NAME> scenario` step to `.github/workflows/run-end-to-end.yml`, as https://github.com/DataDog/system-tests/blob/main/.cursor/rules/end-to-end-testing.mdc asks. The scenario must belong to the scenario groups that the official workflow runs, unless its docstring explains why it is opt-in. A PR that removes or renames a scenario must remove or rename that step too.

Why: GitHub CI runs an end-to-end scenario only through its step in that workflow, and the official workflow selects scenarios by group. Without both, the tests of the scenario never run in CI.

Detect: A new scenario has no step with `contains(inputs.scenarios, '"<NAME>"')`, or it leaves the default groups without an explanation. A removed scenario keeps its step.

Example: Bad: a PR adds a scenario with no run step and outside every default group. Good: the same PR adds the run step and keeps the scenario in its groups, or documents why it is opt-in.

Evidence:

• https://github.com/DataDog/system-tests/pull/8080#discussion_r4338075065
• https://github.com/DataDog/system-tests/pull/7298#pullrequestreview-4702191422
• https://github.com/DataDog/system-tests/pull/7518
