import yaml
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def load_schema(category: str) -> dict[str, Any]:
    def read_yaml(name: str) -> dict[str, Any]:
        with open(SCHEMAS_DIR / f"{name}.yaml") as f:
            return yaml.safe_load(f)

    generic = read_yaml("generic")
    specific = read_yaml(category)

    def merge_span_attributes() -> dict[str, list[str]]:
        generic_attrs = generic.get("span_attributes", {})
        specific_attrs = specific.get("span_attributes", {})

        mandatory = set(generic_attrs.get("mandatory", [])) | set(specific_attrs.get("mandatory", []))
        best_effort = set(generic_attrs.get("best_effort", [])) | set(specific_attrs.get("best_effort", []))

        return {
            "mandatory": list(mandatory),
            "best_effort": list(best_effort),
        }

    def merge_deprecated_aliases() -> dict[str, list[str]]:
        generic_aliases = generic.get("deprecated_aliases", {})
        specific_aliases = specific.get("deprecated_aliases", {})

        combined = dict(generic_aliases)  # shallow copy
        for key, aliases in specific_aliases.items():
            combined.setdefault(key, []).extend(aliases)

        # Deduplicate
        return {k: list(set(v)) for k, v in combined.items()}

    return {
        "required_span_attributes": merge_span_attributes(),
        "deprecated_aliases": merge_deprecated_aliases(),
    }
