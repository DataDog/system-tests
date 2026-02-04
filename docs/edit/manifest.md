Use the manifest files under the [manifests](../../manifests/) folder to declare what will be tested vs skipped, and under what conditions. Tests are identified by `file path` + `Test_Class_Name` +`Test_Name` (All optional, where `Test_Name` is used to differentiate between multiple test functions within a class).
Example weblog test:
```yaml
tests/specific.py: v1.40.0
```
Example Parametric test:
```yaml
tests/parametric/specific_parametric.py: v1.40.0
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
- An error will occur if a manifest file refers to a directory/file/class/function that does not exists
- **After modifying any manifest file, always run `./format.sh`** to validate syntax and sort entries alphabetically.

The example below shows a combination of options that can be deployed in manifest files.

## Example

```yaml
refs:
  - &5_6_and_someid_backports '>=5.6 || ^4.3.0 || ^4.3.0'

manifest:
    tests/specific.py: irrelevant (see this link) # let skip  an entire file
    tests/appsec/test_distributed.py::Test_FeatureA: v1.14 # declare a version for a class
    tests/appsec/test_distributed.py::Test_FeatureB: flaky # skip a class with bug, flaky, irrelevant ...
    tests/appsec/test_distributed.py::Test_FeatureC: # declare a version for a class, depending on weblog
        - weblog_declaration:
            '*': missing_feature # All other weblogs: not yet available
            django: v1.2
            flask: v1.3
            uwsgi: bug (jira ticket) # For a weblog, skip it with bug, or flaky

    # declare compatibility for multiple release lines
    # the caret character locks the major version (ie: `(>=1.3.0 && <2.0.0) || >= 2.3.0`)
    tests/appsec/test_distributed.py::Test_FeatureD: ^1.3.0 || >=2.3.0

    # reference an alias to avoid repeating long or complex semver versions
    tests/appsec/test_distributed.py::Test_FeatureE: *5_6_and_someid_backports
```

## Advanced Syntax Examples

The following examples demonstrate more complex manifest patterns. For reference test manifests, see `tests/test_the_test/manifests/`.

### YAML References for Weblog Groups

Define reusable weblog lists to avoid repetition:

```yaml
refs:
  - &django_weblogs "django-poc, django-py3.13, python3.12"
  - &legacy_weblogs "flask-poc, uwsgi-poc"

manifest:
  tests/appsec/test_feature.py::Test_Feature:
    - weblog_declaration:
        "*": missing_feature
        *django_weblogs: "v3.12.0.dev"  # All Django variants enabled at this version
```

### Explicit Format with Weblog Filtering

Use `weblog` or `excluded_weblog` to target specific weblogs with version conditions:

```yaml
refs:
  - &django_weblogs "django-poc, django-py3.13, python3.12"

manifest:
  # Apply to specific weblogs only
  tests/appsec/iast:
    - component_version: "<3.11.0"
      declaration: missing_feature (JIRA-12345 description of the issue)
      weblog: *django_weblogs

  # Exclude specific weblogs (apply to all others)
  tests/appsec/api_security/test_endpoint_discovery.py:
    - excluded_weblog: [django-py3.13, django-poc, python3.12]
      component_version: "<3.13.0-dev"
      declaration: missing_feature

  # Target a single weblog
  tests/appsec/api_security/test_endpoint_discovery.py::Test_Discovery:
    - weblog: django-poc
      component_version: "<3.12.0-dev"
      declaration: missing_feature
```

### Weblog Lists in Explicit Format

Combine YAML references with arrays:

```yaml
refs:
  - &django_weblogs "django-poc, django-py3.13, python3.12"

manifest:
  tests/appsec/iast/test:
    - component_version: "<3.11.0"
      declaration: irrelevant
      weblog: [*django_weblogs, fastapi]  # Combines reference with additional weblog
```

### Directory-Level Rules

Apply rules to entire directories:

```yaml
manifest:
  # All tests in the sink subdirectory
  tests/appsec/iast/sink: "missing_feature"

  # More specific rules override directory rules
  tests/appsec/iast/sink/test_specific.py: "v2.0.0"
```

### Combining Weblog Declaration with Wildcard Override

```yaml
manifest:
  tests/appsec/api_security/test_schemas.py::Test_Scanners:
    - weblog_declaration:
        "*": "v2.4.0"        # Default: enabled from v2.4.0
        fastapi: missing_feature  # Override: not yet implemented for fastapi

  tests/appsec/api_security/test_schemas.py::Test_Schema_Request_Cookies:
    - weblog_declaration:
        "*": "v2.1.0"        # Default version
        fastapi: "v2.5.0"    # Fastapi needs a later version
```

### Agent Manifest Examples

The `agent.yml` manifest uses the same syntax for agent version conditions:

```yaml
manifest:
  tests/otel_tracing_e2e/test_e2e.py::Test_OTelLogE2E: "v7.48.0"
  tests/test_sampling_rates.py::Test_SamplingRates: "v7.33.0"
  tests/test_telemetry.py::Test_APMOnboardingInstallID: "v7.50.0"
```

#### Notes
- The wildcard `*` is supported for weblog declarations. This will associate missing_feature/bug/flaky/etc. marking to all unspecified weblog variables.
- Manifests support the full npm syntax for SemVer specification. See more at: https://github.com/npm/node-semver#ranges

## Advanced Syntax

Beyond simple version declarations and weblog_declaration, manifests support more complex patterns for fine-grained control. These examples are inspired by real-world usage in `tests/test_the_test/manifests/`.

### YAML Anchors for Weblog Lists

Define reusable weblog lists at the top of your manifest:

```yaml
refs:
  - &django "django-poc, django-py3.13, python3.12"
  - &flask "flask-poc, uwsgi-poc, uds-flask"

manifest:
  tests/appsec/test_endpoint.py::Test_Endpoint:
    - weblog_declaration:
        "*": missing_feature
        *django: v3.12.0.dev  # Apply to all django weblogs
```

### Explicit Declaration with Version Constraint

Use `declaration` with `component_version` for version-specific markers:

```yaml
manifest:
  # Missing feature only for versions below 3.11.0
  tests/appsec/iast:
    - component_version: "<3.11.0"
      declaration: missing_feature (APPSEC-57830 reason here)

  # Bug in a specific version range
  tests/appsec/test_example.py::TestClass::test_method:
    - declaration: bug (JIRA-123)
      component_version: '>=1.9.0'
```

### Weblog Inclusion with `weblog` Field

Apply a declaration only to specific weblogs using a list:

```yaml
manifest:
  # Missing feature only for specific weblogs
  tests/appsec/test_feature.py::TestFeature:
    - declaration: missing_feature
      weblog: [sinatra14, sinatra22, sinatra32]

  # Bug specific to one weblog with version constraint
  tests/appsec/test_other.py:
    - declaration: bug (TICKET-456)
      component_version: "<3.13.0-dev"
      weblog: django-poc
```

### Weblog Exclusion with `excluded_weblog` Field

Apply a declaration to all weblogs except those listed:

```yaml
manifest:
  # Missing feature for all weblogs EXCEPT rack
  tests/appsec/api_security/test_schemas.py::Test_Scanners:
    - declaration: missing_feature (performance impact)
      excluded_weblog: [rack]
```

### Combining Weblog and Excluded Weblog

Apply different declarations to different weblog groups:

```yaml
manifest:
  tests/appsec/test_event.py::Test_Event:
    # First: specific declaration for certain weblogs
    - declaration: irrelevant
      weblog: [rack, rails42]
    # Second: different declaration for remaining weblogs
    - declaration: missing_feature
      excluded_weblog: [rack, rails42]
```

### Multiple Declarations per Test Node

Apply multiple independent conditions to the same test:

```yaml
manifest:
  tests/appsec/iast/test_example.py:
    # Condition 1: version constraint with weblog filter
    - component_version: "<3.11.0"
      declaration: missing_feature (reason 1)
      weblog: *django
    # Condition 2: different version constraint with multiple weblogs
    - component_version: "<3.11.0"
      declaration: irrelevant
      weblog: [*django, fastapi]
```

### Complete Complex Example

Here's a comprehensive example combining multiple advanced features:

```yaml
refs:
  - &django "django-poc, django-py3.13, python3.12"
  - &flask "flask-poc, uwsgi-poc, uds-flask"
  - &v2_backports '>=2.6.0 || ^1.5.0'

manifest:
  # Simple version declaration
  tests/appsec/test_simple.py::TestSimple: v2.6.0

  # Weblog-specific versions using anchors
  tests/appsec/test_endpoint.py::Test_Endpoint:
    - weblog_declaration:
        "*": missing_feature
        *django: v3.12.0.dev

  # Version constraint with declaration
  tests/appsec/iast/sink:
    - component_version: "<3.11.0"
      declaration: missing_feature (APPSEC-57830)
      weblog: *django

  # Exclusion pattern
  tests/appsec/test_schemas.py::Test_Scanners:
    - declaration: missing_feature (performance impact)
      excluded_weblog: [rack]

  # Multiple conditions for the same test
  tests/test_config.py::Test_Config:
    - declaration: bug (APMAPI-1702)
      weblog: [rails52, rails80, rails61]
    - declaration: missing_feature (unknown version)
      excluded_weblog: [rails52, rails80, rails61, rack]

  # Backport version reference
  tests/appsec/test_backport.py::TestBackport: *v2_backports
```

#### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `declaration` | string | Marker with optional reason: `bug (JIRA-123)`, `missing_feature`, `irrelevant`, `flaky` |
| `component_version` | string | SemVer range: `<1.0.0`, `>=2.0.0`, `^1.3.0 \|\| >=2.0.0` |
| `weblog` | string or list | Include only these weblogs |
| `excluded_weblog` | list | Exclude these weblogs (applies to all others) |
| `weblog_declaration` | map | Per-weblog declarations with `*` as default |

**Note:** You cannot use both `weblog` and `excluded_weblog` in the same declaration block. Use multiple declaration blocks instead.

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
  - Complex skip conditions that cannot be expressed with simple version requirements

### In Practice

The manifest approach has proven to be transformative for the system-tests workflow. Teams can independently update their support status, CI pipelines run more efficiently, and the development process is more streamlined.

For searching across libraries, a simple "Find in Files" for your class name in your IDE will show you where it's referenced in all manifests, providing a comprehensive view of support.

## Context and legacy way

The legacy way to declare what will be tested or not are decorators (`@released`, `@bug`, `@missing_feature`...). This solution offers several advantages:

- Declarations are as close as possible to the test, making the link obvious
- Complex conditions (several components involved, complex version range...) are easy to implement, as they're declared as Python code

Unfortunately, it comes with a major drawback: as those declarations are in test files, among all other declarations, activating a single test can become a nightmare due to conflicts between PRs. It also requires approval from the R&P team, slowing the process.
