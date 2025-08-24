# Compliance Schemas

Each YAML file in this directory defines the required attributes for spans in a particular integration category.

## Files

- `generic.yaml`: Contains attributes required for **all** spans, regardless of integration type.
- `<category>.yaml`: Contains attributes specific to that integration category (e.g., `web_frameworks.yaml`, `databases.yaml`).

## Schema Structure

Each schema can define the following sections:

```yaml
span_attributes:
  mandatory:
    - <required_attribute1>
    - <required_attribute2>
  best_effort:
    - <optional_attribute1>
    - <optional_attribute2>

# Deprecated attribute aliases
deprecated_aliases:
  <current_attribute>:
    - <deprecated_name1>
    - <deprecated_name2>
```

## Attribute Types

- `mandatory`: Attributes that must be present for the span to be considered compliant
- `best_effort`: Optional attributes that are recommended but not required. These are currently no-op in the test.
- `deprecated_aliases`: Alternative attribute names that are considered deprecated but still accepted

## Best Practices

1. Keep schemas focused and minimal:
   - Put common attributes in `generic.yaml`
   - Put integration-specific attributes in category files
   - Avoid duplicating keys between files

2. Document deprecated attributes:
   - Use `deprecated_aliases` to maintain backward compatibility
   - List all known alternative names for an attribute
