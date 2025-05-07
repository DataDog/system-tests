# Compliance Schemas

Each YAML file in this directory defines the required, **mandatory** root span attributes for a particular integration category.

## Files

- `base.yaml`: Contains attributes required for **all** spans, regardless of integration type.
- `<category>.yaml`: Contains attributes specific to that integration category (e.g., `web_frameworks.yaml`).

## Format

Each schema must define the following structure:

```yaml
required_root_span_attributes:
  - key1
  - key2
  - ...
```

Use dot notation for nested keys, such as:
- `meta.http.status_code`
- `metrics.process_id`

## Best Practices
- Avoid duplicating keys between base.yaml and category-specific files.
- Keep schema files small and descriptive.
- Treat these schemas as contract definitions for span shape.