### META-001: Manifests Over Decorators
- Severity: P0
- Flag: If a PR adds `@missing_feature`, `@bug`, `@irrelevant`, or `@flaky` decorators whose condition depends **only** on library name, library version, or weblog variant, flag it: the manifest file should be used instead.
- Ref: [Manifest](../../../docs/edit/manifest.md), [Skip tests](../../../docs/edit/skip-tests.md)

### META-002: Manifest Version Prefix
- Severity: P1
- Flag: Versions in manifest files must use the `v` prefix for "this version and above" semantics (e.g., `v1.2.0`). A bare `1.2.0` means **exactly** that version only. Flag bare versions and ask if `v` prefix was intended.
- Detect: A manifest contains a bare version; ask whether the `v` prefix was intended.
- Not when: The bare version is an intentional exact-version declaration, including a development version used to avoid matching an older release candidate as described by META-007.
- Ref: [Manifest](../../../docs/edit/manifest.md)

### META-003: Use irrelevant only when the feature does not apply
- Severity: P1
- Flag: When a test remains but is deactivated for a library, keep the node and use the declaration that matches the cause. Use `irrelevant` only when the feature does not apply to that library.
- Detect: A manifest uses `irrelevant` for a test whose actual cause is a bug, a missing feature, flaky behavior, or an incomplete test application.
- Not when: The feature does not apply to that library, and the declaration says so.
- ✅ Keep the test and declare it `irrelevant (GraalVM. Tracing support only)` for a weblog that cannot produce the span.
- ❌ Declare `irrelevant (AIDM-594)` when AIDM-594 is a tracer bug. Use `bug (AIDM-594)`.
- Ref: [Declaration decorators](../../../docs/edit/skip-tests.md#declaration-decorators)

### META-004: Quote special YAML characters in manifest values
- Severity: P2
- Flag: Values that contain `:`, `#`, `<`, or `>` should be quoted, even when the YAML parser accepts them unquoted, because they are easy to misread.
- Detect: A manifest value contains one of these characters without quotes.
- Not when: The value is already quoted, or the character appears inside a quoted string.
- ✅ `component_version: '<1.2.0'`
- ❌ `component_version: <1.2.0`
- Ref: [Manifest](../../../docs/edit/manifest.md)

### META-005: Use weblog scenario exclusions only for weblog-specific incompatibilities
- Severity: P0
- Flag: `excluded_scenarios` removes the entire weblog–scenario combination from the generated CI matrix and takes precedence over `supported_scenarios` and category matching. Use it only when that specific weblog is incompatible with a scenario that would otherwise select it; do not use it to deactivate individual tests or hide a tracer failure.
- Detect: A `weblog_metadata.yml` entry adds `excluded_scenarios` without a concrete weblog-specific incompatibility, excludes a scenario to avoid one or more failing tests, or uses an exclusion where a manifest declaration or test decorator should express the test-level cause.
- Not when: The excluded scenario would otherwise select the weblog and the entry documents a concrete incompatibility of that weblog, such as an unsupported transport or an application freeze.
- ✅ Exclude `APPSEC_MISSING_RULES` for a specific `httpd` weblog when that application freezes if the rules file is missing, and document the reason next to the exclusion.
- ❌ Exclude an entire scenario for a weblog because one test has a tracer bug; keep the weblog–scenario job and declare that test in the library manifest instead.
- Ref: [Weblog scenario matching](../../../docs/understand/weblogs/weblog-metadata.md#scenario-matching-categories-supported_scenarios-excluded_scenarios)

### META-006: Match each manifest marker to its cause.
- Old_id: claude-07
- Severity: P1
- Flag: Pick the marker that matches the cause. When one PR excludes tests for different causes, give each exclusion its own reason, and make each reason state the real cause. By default, markers other than `irrelevant` and `flaky` become a non-strict xfail, and `conftest.py` also records a fixture error as `xfailed`. When a marked test fails before its assertions, the reason must name that failure.
- Detect: A marker contradicts its cause. Several exclusions with different causes share one vague reason or carry no reason. A marked test fails in setup on invalid configuration or a missing secret, and the marker does not say so.
- ✅ Use `incomplete_test_app (weblog has no /ffe endpoint)` when the weblog does not implement the endpoint.
- ❌ Use `missing_feature` for an endpoint that the weblog does not implement. Set `DD_TRACE_AGENT_PORT` to the literal `agent.port`, causing the library to exit at startup while the run reports an expected failure.
- Ref: [Declaration decorators](../../../docs/edit/skip-tests.md#declaration-decorators)

### META-007: Do not let a minimum dev version match an older release candidate.
- Old_id: cursor-08
- Severity: P1
- Flag: Do not declare a minimum dev version, such as `v4.15.0-dev`, when a release candidate (RC) of that version lacks the feature. Use the exact version without the `v` prefix until a release contains the feature. Then switch back to a minimum version.
- Detect: A manifest declares a minimum dev version, and an RC of that version predates the change.
- Not when: A bare dev version intentionally prevents an older release candidate from matching.
- ✅ Use `Test_Foo: 4.15.0-dev` until a release that contains the feature, such as `4.15.0`, then use `Test_Foo: v4.15.0`.
- ❌ Use `Test_Foo: v4.15.0-dev` while `4.15.0-rc1` lacks the feature.
- Ref: [Simple manifest version](../../../docs/edit/manifest.md#simple-version)

### META-008: Do not hide a documented feature behind NOT_REPORTED_ID.
- Old_id: claude-06
- Severity: P0
- Flag: A feature whose docstring links a Feature Parity Dashboard entry must pass that id as `feature_id`, not `NOT_REPORTED_ID`.
- Detect: A feature in `utils/_features.py` links `feature-parity.us1.prod.dog/#/?feature=<n>` and passes `feature_id=NOT_REPORTED_ID`. A PR adds a feature that passes `feature_id=NOT_REPORTED_ID` and has no dashboard link.
- ✅ The docstring links `?feature=544` and the code passes `feature_id=544`.
- ❌ The docstring links `?feature=544` and the code passes `feature_id=NOT_REPORTED_ID`.
- Ref: [Create a feature](../../../docs/edit/features.md#hello-world-test)

### META-009: Register named end-to-end scenarios in the GitHub workflow.
- Old_id: claude-02
- Severity: P0
- Flag: A PR that adds a named end-to-end scenario must add its `Run <NAME> scenario` step to `.github/workflows/run-end-to-end.yml`. A PR that removes or renames a scenario must remove or rename that step too.
- Detect: A non-`DEFAULT` scenario has no step with `contains(inputs.scenarios, '"<NAME>"')`, or a removed or renamed scenario keeps a stale step.
- Not when: The change targets the `DEFAULT` scenario. Its workflow step already exists, so it does not require a new named step.
- ✅ Add, remove, or rename the workflow step in the same PR as the scenario.
- ❌ Add a named scenario without its workflow step, even when its scenario groups are otherwise valid.
- Ref: [End-to-end testing rules](../end-to-end-testing.md)

### META-010: Gate each method at the versions that have its behavior.
- Severity: P0
- Flag: A version gate that lets a method run on a release without its behavior. If a manifest activates a class or a file at one version, every method must pass from that version. If a method needs a later version, add a method-level entry with that version. If a later release changes the asserted behavior, the range must end before that release. If a change ships on several active release lines, the range must cover each line.
- Detect: A class-level or file-level entry sets one version, and a method asserts behavior that a later release added. A version floor has no upper bound, and a later release changed the asserted behavior. A version range in a manifest or in `tests/parametric/capabilities.yml` omits an active release line with the same change.

### META-011: Link a test class to the RFC that it implements.
- Severity: P1
- Flag: A test class that implements an RFC and has no `@rfc` decorator. If an RFC defines the behavior that a test class checks, the class must carry `@rfc("<link>")` from `utils`.
- Detect: A new test class checks behavior from an RFC that the PR or the feature names. The class has no `@rfc` decorator.
