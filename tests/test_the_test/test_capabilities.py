"""Tests for the capabilities.yml file validation and structure."""

import json
from pathlib import Path

import jsonschema
import yaml

from utils import scenarios
from utils.dd_constants import Capabilities


@scenarios.test_the_test
class TestCapabilities:
    def test_capabilities_yaml_format(self):
        """Validate capabilities.yml against its JSON schema."""
        capabilities_file = Path("tests/parametric/capabilities.yml")
        schema_file = Path("tests/parametric/capabilities_schema.json")

        assert capabilities_file.exists(), f"capabilities.yml not found at {capabilities_file}"
        assert schema_file.exists(), f"capabilities_schema.json not found at {schema_file}"

        # Load files
        with open(capabilities_file, encoding="utf-8") as f:
            capabilities_data = yaml.safe_load(f)

        with open(schema_file, encoding="utf-8") as f:
            schema = json.load(f)

        # Validate against schema
        try:
            jsonschema.validate(instance=capabilities_data, schema=schema)
        except jsonschema.ValidationError as e:
            raise AssertionError(f"capabilities.yml failed schema validation: {e.message}") from e

    def test_all_capability_names_exist(self):
        """Ensure all capability names in capabilities.yml are valid Capabilities enum values."""
        capabilities_file = Path("tests/parametric/capabilities.yml")

        with open(capabilities_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        valid_capability_names = {cap.name for cap in Capabilities}
        errors = []

        for language, lang_config in data["capabilities"].items():
            for version_key, cap_list in lang_config.items():
                for cap_name in cap_list:
                    if cap_name not in valid_capability_names:
                        errors.append(
                            f"Language '{language}', version key '{version_key}': "
                            f"Unknown capability '{cap_name}'. "
                            f"Valid capabilities: {sorted(valid_capability_names)}"
                        )

        if errors:
            raise AssertionError("Invalid capability names found:\n" + "\n".join(errors))

    def test_no_duplicate_capabilities(self):
        """Ensure no capability is listed multiple times for the same language/version."""
        capabilities_file = Path("tests/parametric/capabilities.yml")

        with open(capabilities_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        errors = []

        for language, lang_config in data["capabilities"].items():
            for version_key, cap_list in lang_config.items():
                if len(cap_list) != len(set(cap_list)):
                    duplicates = [cap for cap in cap_list if cap_list.count(cap) > 1]
                    errors.append(
                        f"Language '{language}', version key '{version_key}': Duplicate capabilities: {set(duplicates)}"
                    )

        if errors:
            raise AssertionError("Duplicate capabilities found:\n" + "\n".join(errors))

    def test_base_capabilities_exist(self):
        """Ensure every language has a 'base' capability set."""
        capabilities_file = Path("tests/parametric/capabilities.yml")

        with open(capabilities_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        errors = []

        for language, lang_config in data["capabilities"].items():
            if "base" not in lang_config:
                errors.append(f"Language '{language}' is missing required 'base' capability set")

        if errors:
            raise AssertionError("Missing base capability sets:\n" + "\n".join(errors))
