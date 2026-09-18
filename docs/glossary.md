# Glossary

## Target artifact staging

- target artifact: The library, layer, image, module, release, or workflow artifact selected for a system-tests target such as `python`, `java`, `c`, or `cpp_nginx`.
- dependency artifact: A supporting artifact that is not the selected test target, such as the Datadog Agent image.
- overlay artifact: A supplemental artifact layered onto tests without being the selected test target, such as the WAF rule set.
- artifact staging: The step that resolves target artifact inputs and writes generated artifact entries into `binaries/` before a Docker build or test run consumes them.
- artifact entry: A generated text file in `binaries/` that tells an installer which target artifact to use.
- bounded artifact selector: A selector with stable meaning, such as a commit SHA, release tag, package version, or OCI digest.
- selection marker: A generated artifact entry that records the bounded selector when another entry must use a provider-specific fetch selector.
- payload override: A manual payload placed in `binaries/`, such as a jar, wheel, archive, native module, or local checkout, that takes precedence over generated artifact entries.
- artifact manifest: The generated `binaries/.target-artifacts-manifest.json` file that tracks ownership and hashes for generated artifact entries.

## Test activation/deactivation

- successful: A test is successful if none of its assertions are failing
- unsuccessful: A test is unsuccessful if any of its assertions are failing
- enabled: When a test is enabled, it must be successful for the run to be successful (otherwise the CI fails)
- disabled: A test is disabled when it is marked with `bug`, `missing_feature`, `flaky`, `irrelevant`, or `incomplete_test_app`. Disabled tests don't cause CI to fail regardless of their outcome but are still executed (see skipped for exceptions)
- pass: A test passes when it is enabled and successful
- fail: A test fails when it is enabled and unsuccessful
- xpass: A test is xpass when it is successful but is disabled (not enabled). Indicates an "easy win" opportunity to enable the test
- xfail: A test is xfail when it is unsuccessful and disabled (not enabled). xfail tests are still executed
- skipped: A test is skipped when it is not executed at all (e.g., `irrelevant` or `flaky` marked tests, or deactivated tests marked with `@slow` or `@scenario_crash`)
- easy win: another name for xpass. Comes from the fact that enabling xpasses is easy and prevents regressions
