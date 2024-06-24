# RFC status

- Initiated : June 2023
- Validated : july 2023
- Implemented : August 2023

### Context

The usual way to declare what will be tested or not are decorators (`@released`, `@bug`, `@missing_feature`...). This solution offers several advantages :

- declarations are as close as possible to the test, making the link obvious
- and complex condition (several components involved, complex version range...) is easy to do, as it's declared as python code

### Issue

Unfortunatly, it comes with a major drawback: Activating a single test can become a hell due to confilct between PRs.

### Proposition

To solve this, we'll try to leverage two points :

1. Often, those declarations involve only one component
1. Often, a component is modified by only one developper

The idea is to offer an alternative way to declare those metadata, using one file per component, also known as manifest file. Those files will be inside system tests repo, declaring for a given component some metadata.

Pro :

- Will solve the majority of conflict during test activation PRs
- each team will have ownership of its manifest file, easing the PR preview process

Cost :

- declarations will be a little bit far away from the test, asking a small addition in the learning curve
- re-naming will be a little bit harder, and will spam all teams

## Implementation

- Manifests files will be inside `utils/manifest/`, one per team (each tracer, agent, ASM rules file, any php extension...), named with the argument name used in decorators (`utils/manifest/golang.yml`, `utils/manifest/agent.yml`...)
- Each team will have ownership of its manifest file
- pytest will load those files, and decorate tests node during collection
- Manifest file will be validated using JSON schema in system tests CI
- An error will pop if a manifest file refers to a file/class that does not exists

## Supported features

Will support:

- declaring a skip reason (bug, flaky, irrelevant, missing_feature) for entire file
- declaring released version (or a skip reason) for a class
- declaring released version (or a skip reason) for a class, with details for weblog variants
- The wildcard `*` is supported for weblog declarations

Won't support:

- any complex logic
  \_ because there is not limit on the complexity. We need to draw a line based on the ratio format simplicity / number of occurrences. The cutoff point is only test classes, declaring version for weblog variants, or skip reason for the entire class.
- declaring metadata (bug, flaky, irrelevant) for test methods
  - because their namings are not stable, it would lead to frequent modifications of manifest files, spaming every team
  - because conflict mostly happen at class level

## Example

```yaml
tests/:
  specific.py: irrelevant (see this link) # let skip  an entire file

  appsec/: # more regular declarations:
    test_distributed.py:
      Test_FeatureA: v1.14 # declare a version for a class

      Test_FeatureB: flaky # skip a class with bug, flaky, irrelevant ...

      Test_FeatureC: # declare a version for a class, depending on weblog
        django: v1.2
        flask: v1.3
        uwsgi: bug (jira ticket) # For a weblog, skip it with bug, or flaky
        "*": missing_feature # All other weblogs: not yet available
```

## Format \[WIP\]

```json
{
  "type": "object",

  "properties": {
    "tests/": { "$ref": "#/$defs/folder_content" }
  },

  "$defs": {
    "folder_content": {
      "type": "object",
      "patternProperties": {
        ".+/": { "$ref": "#/$defs/folder_content" },
        "test_.+\\.py": { "$ref": "#/$defs/file_content" }
      }
    },

    "file_content": {
      "oneOf": [
        {
          "type": "object",
          "patternProperties": {
            "Test_.+": {
              "$comment": "It can be a version number, a skip reason, or an object with weblog variant as keys",
              "oneOf": [
                { "$ref": "#/$defs/version" },
                {
                  "type": "object",
                  "$comment": "Keys are weblog variant names, values are version, or a skip reason",
                  "patternProperties": {
                    ".+": { "$ref": "#/$defs/class_content" }
                  }
                }
              ]
            }
          }
        },
        {
          "$ref": "#/$defs/skipped_declaration"
        }
      ]
    },

    "class_content": {
      "oneOf": [
        { "$ref": "#/$defs/version" },
        { "$ref": "#/$defs/skipped_declaration" }
      ]
    },

    "version": { "type": "string", "pattern": "v.+" },

    "skipped_declaration": {
      "type": "string",
      "pattern": "^(bug|flaky|irrelevant|missing_feature)( \\(.+\\))?$"
    }
  }
}
```
