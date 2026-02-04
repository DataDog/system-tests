# Glossary

## Test activation/deactivation

- successful: A test is successful if none of its assertions are failing
- unsuccessful: A test is unsuccessful if any of its assertions are failing
- enabled: When a test is enabled, it must be successful for the run to be successful (otherwise the CI fails)
- disabled: A test is disabled when it is marked with `bug`, `missing_feature`, `flaky`, or `irrelevant`. Disabled tests don't cause CI to fail regardless of their outcome
- pass: A test passes when it is enabled and successful
- fail: A test fails when it is enabled and unsuccessful
- xpass: A test is xpass when it is successful but is disabled (not enabled). Indicates an "easy win" opportunity to enable the test
- xfail: A test is xfail when it is unsuccessful and disabled (not enabled). xfail tests are still executed (except `flaky` and `irrelevant` which are skipped)
- skipped: A test is skipped when it is not executed at all (e.g., `irrelevant` or `flaky` marked tests)
- easy win: another name for xpass. Comes from the fact that enabling xpasses is easy and prevents regressions
