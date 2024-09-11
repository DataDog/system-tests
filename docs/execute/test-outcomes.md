Each test can be flagged with an expected outcomes, with a declaration in [manifests files](../edit/manifest.md) or using inline decorators (`@bug`, `@missing_features` ...).

Those declaration are interpreted by system-tests and impacts the test execution, and the outcome of the entire run :

| Declaration            | Test is executed  | Test actual outcome | System test output  | Comment
| -                      | -                 | -                   | -                   | -
| \<no_declaration>      | Yes               | ✅ Pass             | 🟢 Success          | All good :sunglasses:
| Missing feature or bug | Yes               | ❌ Fail             | 🟢 Success          | Expected failure
| Missing feature or bug | Yes               | ✅ Pass             | 🟠 Success          | XPASS: The feature has been implemented, bug has been fixed -> easy win
| Flaky                  | No                | N.A.                | N.A.                | A flaky test doesn't provide any usefull information, and thus, is not executed.
| Irrelevant             | No                | N.A.                | N.A                 | There is no purpose of running such a test
| \<no_declaration>      | Yes               | ❌ Fail             | 🔴 Fail             | Only use case where system test fails : the test should have been ok, and is not
