Each test can be flagged with an expected outcome, with a declaration in [manifests files](../edit/manifest.md) or using inline decorators (`@bug`, `@missing_features` ...).

Those declarations are interpreted by system-tests and impact the test execution and the outcome of the entire run. See [glossary](../glossary.md) for terminology definitions.

| Declaration                                       | Test is executed  | Test actual outcome | System test output  | Comment
| -                                                 | -                 | -                   | -                   | -
| \<no_declaration>                                 | Yes               | ✅ Successful       | 🟢 Pass             | All good :sunglasses:
| Missing feature or bug or incomplete test app     | Yes               | ❌ Unsuccessful     | 🟢 xfail            | Test is disabled and unsuccessful (expected behavior)
| Missing feature or bug or incomplete test app     | Yes               | ✅ Successful       | 🟠 xpass            | Test is disabled but successful -> easy win, time to enable the test
| Flaky                                             | No                | N.A.                | N.A. (skipped)      | A flaky test doesn't provide any useful information, and thus, is skipped
| Irrelevant                                        | No                | N.A.                | N.A. (skipped)      | There is no purpose of running such a test, it is skipped
| \<no_declaration>                                 | Yes               | ❌ Unsuccessful     | 🔴 Fail             | Only use case where system test fails: the test is enabled but unsuccessful
