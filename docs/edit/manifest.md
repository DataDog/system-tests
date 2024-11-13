Use the manifest files under the [manifests](../../manifests/) folder to declare what will be tested vs skipped, and under what conditions. Tests are identified by  `file path` + `Test_Class_Name` +` Optional | Test_Name` (Where `Test_Name` is used to differentiate between multiple test functions within a class).
Example weblog test: 
```yaml
tests/:
  specific.py: v1.40.0
```
Example Parametric test: 
```yaml
tests/:
  parametric/:
    specific_parametric.py: v1.40.0
```

A test is **enabled** if: 
- Nothing is specified in the manifest file and there aren’t conflicting in-line decorators (e.g, @bug, see [skip-tests.md](./skip-tests.md)) on the test
- `label` contains a valid [https://semver.org/] version number.

A test is **disabled** if `label` contains some other marker (See Test “Disable” Labels section).

When executed locally, tests run against the latest version of dd-trace by default. In CI, the tests run against the main branch and the latest version.

#### Notes
- Each library team has ownership of its manifest file
- Manifest files are validated using JSON schema in system tests CI
- An error will occur if a manifest file refers to a file/class that does not exists

The example below shows a combination of options that can be deployed in manifest files. 

## Example

```yaml
refs:
  - &5_6_and_someid_backports '>=5.6 || ^4.3.0 || ^4.3.0'

tests/:
  specific.py: irrelevant (see this link) # let skip  an entire file

  appsec/: # more regular declarations:
    test_distributed.py:
      Test_FeatureA: v1.14 # declare a version for a class

      Test_FeatureB: flaky # skip a class with bug, flaky, irrelevant ...

      Test_FeatureC: # declare a version for a class, depending on weblog
        '*': missing_feature # All other weblogs: not yet available
        django: v1.2
        flask: v1.3
        uwsgi: bug (jira ticket) # For a weblog, skip it with bug, or flaky

      # declare compatibility for multiple release lines
      # the caret character locks the major version (ie: `(>=1.3.0 && <2.0.0) || >= 2.3.0`)
      Test_FeatureD: ^1.3.0 || >=2.3.0

      # reference an alias to avoid repeating long or complex semver versions
      Test_FeatureE: *5_6_and_someid_backports
```

#### Notes
- The wildcard `*` is supported for weblog declarations
- Manifests support the full npm syntax for SemVer specification. See more at: https://github.com/npm/node-semver#ranges

## Context and legacy way

The legacy way to declare what will be tested or not are decorators (`@released`, `@bug`, `@missing_feature`...). This solution offers several advantages :

- declarations are as close as possible to the test, making the link obvious
- and complex condition (several components involved, complex version range...) is easy to do, as it's declared as python code

Unfortunatly, it comes with a major drawback: as those declarations are in test files, among all other declarations, activating a single test can become a hell due to confilcts between PRs. It also requires approval for R&P team, slowing the process.
