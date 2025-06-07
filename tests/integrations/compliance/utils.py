import yaml
import json
from pathlib import Path
from typing import Any
from utils import context

# Schema Loading Section
# ---------------------
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


# Report Generation Section
# ------------------------
def generate_compliance_report(
    category: str,
    name: str,
    missing: list[str] | None = None,
    deprecated: list[str] | None = None,
) -> None:
    report: dict[str, Any] = {
        "integration": name,
        "language": context.library.name,
        "status": "pass" if not missing else "fail",
    }

    if deprecated:
        report["deprecated_attributes"] = deprecated
    if missing:
        report["missing_attributes"] = missing

    report_dir = Path(context.scenario.host_log_folder) / "compliance_reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    file_path = report_dir / f"{category}_{name}.json"
    with open(file_path, "w") as f:
        json.dump(report, f, indent=2)


# Validation Section
# -----------------
def _get_nested(d: dict, dotted_key: str):
    keys = dotted_key.split(".")
    if len(keys) > 1 and keys[0] in ("meta", "metrics"):
        keys = [keys[0]] + [".".join(keys[1:])]
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return None
    return d


def assert_required_keys(span: dict, schema: dict) -> tuple[list[str], list[str]]:
    required = schema["required_span_attributes"]
    deprecated_aliases = schema.get("deprecated_aliases", {})

    mandatory_keys = required["mandatory"]
    # best_effort_keys = required.get("best_effort", [])

    missing_keys = []
    deprecated_used = []

    for key in mandatory_keys:
        if _get_nested(span, key) is not None:
            continue

        fallback_keys = deprecated_aliases.get(key, [])
        for fallback in fallback_keys:
            if _get_nested(span, fallback) is not None:
                deprecated_used.append(fallback)
                break
        else:
            missing_keys.append(key)

    # for key in best_effort_keys:
    #    if _get_nested(span, key) is None:
    #        print(f"[BEST-EFFORT] Optional but recommended key not found: {key}")

    return missing_keys, deprecated_used
