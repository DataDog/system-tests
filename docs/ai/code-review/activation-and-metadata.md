### META-001: Manifests Over Decorators
- Flag: If a PR adds `@missing_feature`, `@bug`, `@irrelevant`, or `@flaky` decorators whose condition depends **only** on library name, library version, or weblog variant, flag it: the manifest file should be used instead.
- Ref: [Manifest](../../edit/manifest.md), [Skip tests](../../edit/skip-tests.md)

### META-002: Manifest Version Prefix
- Flag: Versions in manifest files must use the `v` prefix for "this version and above" semantics (e.g., `v1.2.0`). A bare `1.2.0` means **exactly** that version only. Flag bare versions and ask if `v` prefix was intended.
- Detect: A manifest contains a bare version; ask whether the `v` prefix was intended.
- Not when: The bare version is an intentional exact-version declaration, including a development version used to avoid matching an older release candidate as described by META-007.
- Ref: [Manifest](../../edit/manifest.md)

### META-003: Use irrelevant only when the feature does not apply
- Flag: When a test remains but is deactivated for a library, keep the node and use the declaration that matches the cause. Use `irrelevant` only when the feature does not apply to that library.
- Detect: A manifest uses `irrelevant` for a test whose actual cause is a bug, a missing feature, flaky behavior, or an incomplete test application.
- Not when: The feature does not apply to that library, and the declaration says so.
- ✅ Keep the test and declare it `irrelevant (GraalVM. Tracing support only)` for a weblog that cannot produce the span.
- ❌ Declare `irrelevant (AIDM-594)` when AIDM-594 is a tracer bug. Use `bug (AIDM-594)`.
- Ref: [Declaration decorators](../../edit/skip-tests.md#declaration-decorators)

### META-004: Manifest YAML Syntax
- Flag: `bug` and `flaky` markers must include a JIRA ticket (e.g., `bug (JIRA-123)`). Values with special YAML characters (`>`, `<`, `:`, `#`) must be quoted. Entries should be sorted alphabetically within each manifest file.

### META-005: Use weblog scenario exclusions only for weblog-specific incompatibilities
- Flag: `excluded_scenarios` removes the entire weblog–scenario combination from the generated CI matrix and takes precedence over `supported_scenarios` and category matching. Use it only when that specific weblog is incompatible with a scenario that would otherwise select it; do not use it to deactivate individual tests or hide a tracer failure.
- Detect: A `weblog_metadata.yml` entry adds `excluded_scenarios` without a concrete weblog-specific incompatibility, excludes a scenario to avoid one or more failing tests, or uses an exclusion where a manifest declaration or test decorator should express the test-level cause.
- Not when: The excluded scenario would otherwise select the weblog and the entry documents a concrete incompatibility of that weblog, such as an unsupported transport or an application freeze.
- ✅ Exclude `APPSEC_MISSING_RULES` for a specific `httpd` weblog when that application freezes if the rules file is missing, and document the reason next to the exclusion.
- ❌ Exclude an entire scenario for a weblog because one test has a tracer bug; keep the weblog–scenario job and declare that test in the library manifest instead.
- Ref: [Weblog scenario matching](../../understand/weblogs/weblog-metadata.md#scenario-matching-categories-supported_scenarios-excluded_scenarios)

### META-006: Match each manifest marker to its cause.
- Old_id: claude-07
- Flag: Pick the marker that matches the cause. When one PR excludes tests for different causes, give each exclusion its own reason, and make each reason state the real cause. By default, markers other than `irrelevant` and `flaky` become a non-strict xfail, and `conftest.py` also records a fixture error as `xfailed`. When a marked test fails before its assertions, the reason must name that failure.
- Detect: A marker contradicts its cause, or several exclusions with different causes share one vague reason. A marked test fails during setup because of invalid configuration or a missing required secret that the marker does not describe.
- ✅ Use `incomplete_test_app (weblog has no /ffe endpoint)` when the weblog does not implement the endpoint.
- ❌ Use `missing_feature` for an endpoint that the weblog does not implement. Set `DD_TRACE_AGENT_PORT` to the literal `agent.port`, causing the library to exit at startup while the run reports an expected failure.
- Ref: [Declaration decorators](../../edit/skip-tests.md#declaration-decorators)

### META-007: Do not let a minimum dev version match an older release candidate.
- Old_id: cursor-08
- Flag: Do not declare a minimum dev version, such as `v4.15.0-dev`, when a release candidate (RC) of that version lacks the feature. Use the exact version without the `v` prefix until a release contains the feature. Then switch back to a minimum version.
- Detect: A manifest declares a minimum dev version, and an RC of that version predates the change.
- Not when: A bare dev version intentionally prevents an older release candidate from matching.
- ✅ Use `Test_Foo: 4.15.0-dev` until a release that contains the feature, such as `4.15.0`, then use `Test_Foo: v4.15.0`.
- ❌ Use `Test_Foo: v4.15.0-dev` while `4.15.0-rc1` lacks the feature.
- Ref: [Simple manifest version](../../edit/manifest.md#simple-version)

### META-008: Do not hide a documented feature behind NOT_REPORTED_ID.
- Old_id: claude-06
- Flag: A feature whose docstring links a Feature Parity Dashboard entry must pass that id as `feature_id`, not `NOT_REPORTED_ID`.
- Detect: A feature in `utils/_features.py` links `feature-parity.us1.prod.dog/#/?feature=<n>` and passes `feature_id=NOT_REPORTED_ID`.
- ✅ The docstring links `?feature=544` and the code passes `feature_id=544`.
- ❌ The docstring links `?feature=544` and the code passes `feature_id=NOT_REPORTED_ID`.
- Ref: [Create a feature](../../edit/features.md#hello-world-test)

### META-009: Make a new scenario reachable by CI.
- Old_id: claude-02
- Flag: A PR that adds an end-to-end scenario must add its `Run <NAME> scenario` step to `.github/workflows/run-end-to-end.yml`. The scenario must belong to the scenario groups that the official workflow runs, unless its docstring explains why it is opt-in. A PR that removes or renames a scenario must remove or rename that step too.
- Detect: A new scenario has no step with `contains(inputs.scenarios, '"<NAME>"')`, or it leaves the default groups without an explanation. A removed scenario keeps its step.
- Not when: The change targets the `DEFAULT` scenario, whose workflow step already exists and does not require registering a new named scenario. An intentionally opt-in scenario may be omitted from the default groups when its docstring explains why, but it still requires its own workflow step.
- ✅ Add the run step and keep the scenario in its groups, or document why it is opt-in.
- ❌ Add a scenario with no run step and outside every default group.
- Ref: [End-to-end testing rules](../../../.cursor/rules/end-to-end-testing.mdc)
