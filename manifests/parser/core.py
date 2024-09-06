from collections import defaultdict
from functools import lru_cache
import json
import os

from jsonschema import validate
import yaml


def _flatten(base, obj):
    if base.endswith(".py"):
        base += "::"
    for key, value in obj.items():

        if isinstance(value, str):
            yield f"{base}{key}", value
        elif isinstance(value, dict):
            if base.endswith(".py::"):
                yield f"{base}{key}", value
            else:
                yield from _flatten(f"{base}{key}", value)


def _load_file(file):

    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return {}

    # this field is only used for YAML templating
    if "refs" in data:
        del data["refs"]

    return {nodeid: value for nodeid, value in _flatten("", data) if value is not None}


@lru_cache
def load(base_dir="manifests/"):
    """
    Returns a dict of nodeid, value are another dict where the key is the component
    and the value the declaration. It is meant to sent directly the value of a nodeid to @released.

    Data example:

    {
        "tests/test_x.py::Test_feature":
        {
            "agent": "v1.0",
            "php": "missing_feature"
        }
    }
    """

    result = defaultdict(dict)

    for component in (
        "agent",
        "cpp",
        "dotnet",
        "golang",
        "java",
        "nodejs",
        "php",
        "python",
        "python_otel",
        "ruby",
    ):
        data = _load_file(f"{base_dir}{component}.yml")

        for nodeid, value in data.items():
            result[nodeid][component] = value

    return result


def assert_key_order(obj: dict, path=""):
    last_key = "/"

    for key in obj:
        if last_key.endswith("/") and not key.endswith("/"):  # transition from folder fo files, nothing to do
            pass
        elif not last_key.endswith("/") and key.endswith("/"):  # folder must be before files
            raise ValueError(f"Folders must be placed before files at {path}/{last_key}")
        else:  # otherwise, it must be sorted
            assert last_key < key, f"Order is not respected at {path} ({last_key} < {key})"

        if isinstance(obj[key], dict):
            assert_key_order(obj[key], f"{path}.{key}")

        last_key = key


def validate_manifest_files():
    with open("manifests/parser/schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    for file in os.listdir("manifests/"):
        if file.endswith(".yml"):
            try:
                with open(f"manifests/{file}", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                # this field is only used for YAML templating
                if "refs" in data:
                    del data["refs"]

                validate(data, schema)
                assert_key_order(data)

            except Exception as e:
                raise ValueError(f"Fail to validate manifests/{file}") from e


if __name__ == "__main__":
    validate_manifest_files()
