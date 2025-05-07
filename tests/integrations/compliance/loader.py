import yaml
import os

BASE_PATH = os.path.join(os.path.dirname(__file__), "schemas")


def load_schema(category):
    with open(os.path.join(BASE_PATH, "base.yaml")) as f:
        base = yaml.safe_load(f)

    with open(os.path.join(BASE_PATH, f"{category}.yaml")) as f:
        category_specific = yaml.safe_load(f)

    merged = {
        "required_root_span_attributes": (
                base.get("required_root_span_attributes", []) +
                category_specific.get("required_root_span_attributes", [])
        )
    }

    return merged
