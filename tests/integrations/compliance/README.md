# Integration Compliance Tests

This directory contains compliance tests that verify if integration spans (e.g., for web frameworks, databases) include a required set of attributes. These tests are meant to ensure consistent span formatting across libraries.

## Structure

- `test_<category>.py`: The actual compliance test for an integration category (e.g., `test_web_frameworks.py`).
- `loader.py`: Loads and merges base and category-specific schemas.
- `validator.py`: Validates a given span against the merged schema.
- `schemas/`: YAML schema files specifying required attributes for spans.

## Adding a New Category

To test a new integration category (e.g., databases):
- Add a `schemas/<category>.yaml` file with category-specific keys.
- Create a `test_<category>.py` using the shared loader and validator.
- Ensure the weblog simulates an appropriate request to trigger a representative span.