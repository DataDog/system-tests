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
- Nothing is specified in the manifest file and there aren't conflicting in-line decorators (e.g, @bug, see [skip-tests.md](./skip-tests.md)) on the test
- `label` contains a valid [https://semver.org/] version number.
See [enable-test.md](./enable-test.md) to enable a test.

A test is **disabled** if `label` contains some other marker.
See [skip-tests.md](./skip-tests.md) to disable a test.

When executed locally, tests run against the latest version of dd-trace by default. In CI, the tests run against the main branch and the latest version.

#### Notes
- Entries in the manifest file must be sorted in alphabetical order. This is validated by the TEST_THE_TESTS scenario/linter.
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
- The wildcard `*` is supported for weblog declarations. This will associate missing_feature/bug/flaky/etc. marking to all unspecified weblog variables.
- Manifests support the full npm syntax for SemVer specification. See more at: https://github.com/npm/node-semver#ranges

## Why Manifest Files?

### The Evolution from Decorators to Manifest Files

Manifest files weren't always part of system-tests. Understanding their origin helps to appreciate their benefits:

Initially, system-tests used in-line decorators like `@released` to specify test compatibility. While this approach had the benefit of keeping feature support declarations close to the tests themselves, it created significant challenges as the project grew:

1. **Merge conflicts**: With multiple teams working on different features simultaneously, decorators in test files created frequent merge conflicts, as the same files were being modified at the same time by different teams.

2. **CI pipeline delays**: Resolving these conflicts meant restarting CI pipelines, which with growing CI durations could delay PRs for hours.

3. **Approval bottlenecks**: Changes to test files required cross-team reviews, creating bottlenecks in the development process.

### Key Benefits of Manifest Files

The manifest system addresses these challenges by providing:

1. **Reduced conflicts**: By separating feature support declarations from test implementations, conflicts are dramatically reduced. Teams can update their support status without touching test files.

2. **Guild ownership**: Each language team can manage their own manifest without affecting other teams, providing clear ownership and reducing cross-team dependencies.

3. **Feature visibility**: Although you no longer see supported languages directly in test files, manifests provide a better view of what features are supported across versions for each language.

4. **CI efficiency**: Less conflicts means less CI restarts, resulting in faster PR iterations and shorter release cycles.

### Best Practices

- **Test structure**: Design tests around features, with the general rule that one test class = one feature
- **Manifest declarations**: Use manifests to declare at which version of your library a feature should be working
- **When to use decorators**: Decorators still have their place for:
  - Fine-grained skips of specific test methods within a class
  - Complex skip conditions that cannot be expressed with simple version requirements

### In Practice

The manifest approach has proven to be transformative for the system-tests workflow. Teams can independently update their support status, CI pipelines run more efficiently, and the development process is more streamlined.

For searching across libraries, a simple "Find in Files" for your class name in your IDE will show you where it's referenced in all manifests, providing a comprehensive view of support.

## Context and legacy way

The legacy way to declare what will be tested or not are decorators (`@released`, `@bug`, `@missing_feature`...). This solution offers several advantages:

- Declarations are as close as possible to the test, making the link obvious
- Complex conditions (several components involved, complex version range...) are easy to implement, as they're declared as Python code

Unfortunately, it comes with a major drawback: as those declarations are in test files, among all other declarations, activating a single test can become a nightmare due to conflicts between PRs. It also requires approval from the R&P team, slowing the process.
