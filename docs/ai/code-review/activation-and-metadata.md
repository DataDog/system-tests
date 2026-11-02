### META-001: Manifests Over Decorators
- Flag: If a PR adds `@missing_feature`, `@bug`, `@irrelevant`, or `@flaky` decorators whose condition depends **only** on library name, library version, or weblog variant, flag it: the manifest file should be used instead.
- Detect: <TODO_RMM>
- Not when: <TODO_RMM>
- ✅ <TODO_RMM>
- ❌ <TODO_RMM>
- Ref: [Manifest](../../edit/manifest.md), [Skip tests](../../edit/skip-tests.md)

### META-002: Manifest Version Prefix
- Flag: Versions in manifest files must use the `v` prefix for "this version and above" semantics (e.g., `v1.2.0`). A bare `1.2.0` means **exactly** that version only. Flag bare versions and ask if `v` prefix was intended.
- Detect: A manifest contains a bare version; ask whether the `v` prefix was intended.
- Not when: <TODO_RMM>
- ✅ <TODO_RMM>
- ❌ <TODO_RMM>
- Ref: [Manifest](../../edit/manifest.md)

### META-003: Removed or Skipped Tests Need Manifest Entries
- Flag: When a test is removed or permanently skipped for a language, add an `irrelevant` entry in the corresponding manifest file. Otherwise, downstream processes (easy-win) will incorrectly assume the test passes.
- Detect: <TODO_RMM>
- Not when: <TODO_RMM>
- ✅ <TODO_RMM>
- ❌ <TODO_RMM>
- Ref: [Manifest](../../edit/manifest.md)

### META-004: Manifest YAML Syntax
- Flag: `bug` and `flaky` markers must include a JIRA ticket (e.g., `bug (JIRA-123)`). Values with special YAML characters (`>`, `<`, `:`, `#`) must be quoted. Entries should be sorted alphabetically within each manifest file.
- Detect: <TODO_RMM>
- Not when: <TODO_RMM>
- ✅ <TODO_RMM>
- ❌ <TODO_RMM>

### META-005: Deactivating scenarios in weblog_metadata files
- Flag: Deactivating scenarios in weblog_metadata files is rare and should only be done when it aims at deactivating a test or group of tests that runs on multiple scenarios for only one scenario.
- Detect: <TODO_RMM>
- Not when: <TODO_RMM>
- ✅ <TODO_RMM>
- ❌ <TODO_RMM>

### META-006: Match each manifest marker to its cause.
- old_id: claude-07
- Flag: Pick the marker that matches the cause. When one PR excludes tests for different causes, give each exclusion its own reason, and make each reason state the real cause. By default, markers other than `irrelevant` and `flaky` become a non-strict xfail, and `conftest.py` also records a fixture error as `xfailed`. When a marked test fails before its assertions, the reason must name that failure.
- Detect: A marker contradicts its cause, or several exclusions with different causes share one vague reason. A marked test fails during setup because of invalid configuration or a missing required secret that the marker does not describe.
- Not when: <TODO_RMM>
- ✅ Use `incomplete_test_app (weblog has no /ffe endpoint)` when the weblog does not implement the endpoint.
- ❌ Use `missing_feature` for an endpoint that the weblog does not implement. Set `DD_TRACE_AGENT_PORT` to the literal `agent.port`, causing the library to exit at startup while the run reports an expected failure.
- Ref: [Declaration decorators](../../edit/skip-tests.md#declaration-decorators)

### META-007: Do not let a minimum dev version match an older release candidate.
- old_id: cursor-08
- Flag: Do not declare a minimum dev version, such as `v4.15.0-dev`, when a release candidate (RC) of that version lacks the feature. Use the exact version without the `v` prefix until a release contains the feature. Then switch back to a minimum version.
- Detect: A manifest declares a minimum dev version, and an RC of that version predates the change.
- Not when: A bare dev version intentionally prevents an older release candidate from matching.
- ✅ Use `Test_Foo: 4.15.0-dev` until a release that contains the feature, such as `4.15.0`, then use `Test_Foo: v4.15.0`.
- ❌ Use `Test_Foo: v4.15.0-dev` while `4.15.0-rc1` lacks the feature.
- Ref: [Simple manifest version](../../edit/manifest.md#simple-version)

### META-008: Do not hide a documented feature behind NOT_REPORTED_ID.
- old_id: claude-06
- Flag: A feature whose docstring links a Feature Parity Dashboard entry must pass that id as `feature_id`, not `NOT_REPORTED_ID`.
- Detect: A feature in `utils/_features.py` links `feature-parity.us1.prod.dog/#/?feature=<n>` and passes `feature_id=NOT_REPORTED_ID`.
- Not when: <TODO_RMM>
- ✅ The docstring links `?feature=544` and the code passes `feature_id=544`.
- ❌ The docstring links `?feature=544` and the code passes `feature_id=NOT_REPORTED_ID`.
- Ref: [Create a feature](../../edit/features.md#hello-world-test)

### META-009: Make a new scenario reachable by CI.
- old_id: claude-02
- Flag: A PR that adds an end-to-end scenario must add its `Run <NAME> scenario` step to `.github/workflows/run-end-to-end.yml`. The scenario must belong to the scenario groups that the official workflow runs, unless its docstring explains why it is opt-in. A PR that removes or renames a scenario must remove or rename that step too.
- Detect: A new scenario has no step with `contains(inputs.scenarios, '"<NAME>"')`, or it leaves the default groups without an explanation. A removed scenario keeps its step.
- Not when: The scenario is intentionally opt-in and its docstring explains why.
- ✅ Add the run step and keep the scenario in its groups, or document why it is opt-in.
- ❌ Add a scenario with no run step and outside every default group.
- Ref: [End-to-end testing rules](../../../.cursor/rules/end-to-end-testing.mdc)
