# Integration Compliance Tests

This directory contains compliance tests that verify if integration spans (e.g., for web frameworks, databases) include a required set of attributes. These tests are meant to ensure consistent span formatting across libraries.

## Structure

- `test_<category>.py`: The actual compliance test for an integration category (e.g., `test_web_frameworks.py`, `test_databases.py`).
- `utils.py`: Contains shared utilities for schema loading, validation, and report generation.
- `schemas/`: YAML schema files specifying required attributes for spans. See [schemas/README.md](schemas/README.md) for details on schema format and best practices.

## How It Works

1. Each test loads a schema that defines required attributes for a specific integration type
2. The schema is merged with a generic schema that contains common requirements
3. Tests validate spans against the merged schema
4. Results are written to individual JSON reports in the `compliance_reports` directory
5. At the end of the test run, all reports are merged into a single `compliance.json` file

## Adding a New Category

To test a new integration category:

1. Add a `schemas/<category>.yaml` file with category-specific keys. See [schemas/README.md](schemas/README.md) for detailed schema format and best practices.

2. Create a `test_<category>.py` using the shared utilities:
```python
from utils import interfaces, weblog, context
from .utils import assert_required_keys, generate_compliance_report, load_schema

class Test_NewCategory:
    def setup_attributes(self):
        # Ensure the weblog simulates an appropriate request to trigger a representative span
        pass

    def test_attributes(self):
        schema = load_schema("<category>")
        span = interfaces.library.get_root_span(self.r)
        missing, deprecated = assert_required_keys(span, schema)
        generate_compliance_report(
            category="<category>",
            name="<integration_name>",
            missing=missing,
            deprecated=deprecated
        )
```
