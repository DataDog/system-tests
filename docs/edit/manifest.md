Manifest file is the usual way to declare what will be tested or not. They are located in `manifests/` folder, and every tracer team got its own manifest file.

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
```

### Implementation

- Manifests files are inside `manifests/` folder, one per team (each library, agent, ASM rules file, any php extension...): `manifests/golang.yml`, `manifest/agent.yml`...
- Each team has ownership of its manifest file
- Manifest file are validated using JSON schema in system tests CI
- An error pops if a manifest file refers to a file/class that does not exists

## Supported features

- declaring a skip reason (bug, flaky, irrelevant, missing_feature) for entire file
- declaring released version (or a skip reason) for a class
- declaring released version (or a skip reason) for a class, with details for weblog variants
- The wildcard `*` is supported for weblog declarations
- Supports the full npm syntax for SemVer specification. See more at: https://github.com/npm/node-semver#ranges

## Will never be supported:

- any complex logic
  \_ because there is not limit on the complexity. We need to draw a line based on the ratio format simplicity / number of occurrences. The cutoff point is only test classes, declaring version for weblog variants, or skip reason for the entire class.
- declaring metadata (bug, flaky, irrelevant) for test methods
  - because their namings are not stable, it would lead to frequent modifications of manifest files, spaming every team
  - because conflict mostly happen at class level

## Context and legacy way

The legacy way to declare what will be tested or not are decorators (`@released`, `@bug`, `@missing_feature`...). This solution offers several advantages :

- declarations are as close as possible to the test, making the link obvious
- and complex condition (several components involved, complex version range...) is easy to do, as it's declared as python code

Unfortunatly, it comes with a major drawback: as those declarations are in test files, among all other declarations, activating a single test can become a hell due to confilcts between PRs. It also requires approval for R&P team, slowing the process.
