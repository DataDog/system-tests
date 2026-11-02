META-001: Manifests Over Decorators
flag: If a PR adds `@missing_feature`, `@bug`, `@irrelevant`, or `@flaky` decorators whose condition depends **only** on library name, library version, or weblog variant, flag it: the manifest file should be used instead.
detect: <TODO_RMM>
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>
ref: [Manifest](../../edit/manifest.md), [Skip tests](../../edit/skip-tests.md)

META-002: Manifest Version Prefix
flag: Versions in manifest files must use the `v` prefix for "this version and above" semantics (e.g., `v1.2.0`). A bare `1.2.0` means **exactly** that version only. Flag bare versions and ask if `v` prefix was intended.
detect: A manifest contains a bare version; ask whether the `v` prefix was intended.
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>
ref: [Manifest](../../edit/manifest.md)

META-003: Removed or Skipped Tests Need Manifest Entries
flag: When a test is removed or permanently skipped for a language, add an `irrelevant` entry in the corresponding manifest file. Otherwise, downstream processes (easy-win) will incorrectly assume the test passes.
detect: <TODO_RMM>
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>
ref: [Manifest](../../edit/manifest.md)

META-004: Manifest YAML Syntax
flag: `bug` and `flaky` markers must include a JIRA ticket (e.g., `bug (JIRA-123)`). Values with special YAML characters (`>`, `<`, `:`, `#`) must be quoted. Entries should be sorted alphabetically within each manifest file.
detect: <TODO_RMM>
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>

META-005: Deactivating scenarios in weblog_metadata files
flag: Deactivating scenarios in weblog_metadata files is rare and should only be done when it aims at deactivating a test or group of tests that runs on multiple scenarios for only one scenario.
detect: <TODO_RMM>
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>

META-006: Match each manifest marker to its cause.
flag: Pick the marker that matches the cause. When one PR excludes tests for different causes, give each exclusion its own reason, and make each reason state the real cause. By default, markers other than `irrelevant` and `flaky` become a non-strict xfail, and `conftest.py` also records a fixture error as `xfailed`. When a marked test fails before its assertions, the reason must name that failure.
detect: A marker contradicts its cause, or several exclusions with different causes share one vague reason. A marked test fails during setup because of invalid configuration or a missing required secret that the marker does not describe.
not when: <TODO_RMM>
ie good: Use `incomplete_test_app (weblog has no /ffe endpoint)` when the weblog does not implement the endpoint.
ie bad: Use `missing_feature` for an endpoint that the weblog does not implement. Set `DD_TRACE_AGENT_PORT` to the literal `agent.port`, causing the library to exit at startup while the run reports an expected failure.
ref: [Declaration decorators](../../edit/skip-tests.md#declaration-decorators)

META-007: Do not let a minimum dev version match an older release candidate.
flag: Do not declare a minimum dev version, such as `v4.15.0-dev`, when a release candidate (RC) of that version lacks the feature. Use the exact version without the `v` prefix until a release contains the feature. Then switch back to a minimum version.
detect: A manifest declares a minimum dev version, and an RC of that version predates the change.
not when: A bare dev version intentionally prevents an older release candidate from matching.
ie good: Use `Test_Foo: 4.15.0-dev` until a release that contains the feature, such as `4.15.0`, then use `Test_Foo: v4.15.0`.
ie bad: Use `Test_Foo: v4.15.0-dev` while `4.15.0-rc1` lacks the feature.
ref: [Simple manifest version](../../edit/manifest.md#simple-version)

META-008: Do not hide a documented feature behind NOT_REPORTED_ID.
flag: A feature whose docstring links a Feature Parity Dashboard entry must pass that id as `feature_id`, not `NOT_REPORTED_ID`.
detect: A feature in `utils/_features.py` links `feature-parity.us1.prod.dog/#/?feature=<n>` and passes `feature_id=NOT_REPORTED_ID`.
not when: <TODO_RMM>
ie good: The docstring links `?feature=544` and the code passes `feature_id=544`.
ie bad: The docstring links `?feature=544` and the code passes `feature_id=NOT_REPORTED_ID`.
ref: [Create a feature](../../edit/features.md#hello-world-test)

META-009: Make a new scenario reachable by CI.
flag: A PR that adds an end-to-end scenario must add its `Run <NAME> scenario` step to `.github/workflows/run-end-to-end.yml`. The scenario must belong to the scenario groups that the official workflow runs, unless its docstring explains why it is opt-in. A PR that removes or renames a scenario must remove or rename that step too.
detect: A new scenario has no step with `contains(inputs.scenarios, '"<NAME>"')`, or it leaves the default groups without an explanation. A removed scenario keeps its step.
not when: The scenario is intentionally opt-in and its docstring explains why.
ie good: Add the run step and keep the scenario in its groups, or document why it is opt-in.
ie bad: Add a scenario with no run step and outside every default group.
ref: [End-to-end testing rules](../../../.cursor/rules/end-to-end-testing.mdc)
