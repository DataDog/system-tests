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

    return {nodeid: value for nodeid, value in _flatten("", data)}


def _fix_irrelevant_legacy(value: [str, dict]):
    # in JSON report, the marker for irrelevant is "not relevant", where the decorator is "irrelevant"
    if isinstance(value, dict):
        return {k: _fix_irrelevant_legacy(v) for k, v in value.items()}

    if value.startswith("irrelevant"):
        return "not relevant" + value[len("irrelevant") :]

    return value


@lru_cache
def load(library):

    result = _load_file(f"manifests/{library}.yml")
    result = {nodeid: _fix_irrelevant_legacy(value) for nodeid, value in result.items() if value is not None}

    return result


def assert_key_order(obj: dict, path=""):
    last_key = "/"

    for key in obj:
        if last_key.endswith("/") and not key.endswith("/"):  # transition from folder fo files, nothing to do
            pass
        elif not last_key.endswith("/") and key.endswith("/"):  # folder must be before files
            raise ValueError("Folders must be placed before files at {path}")
        else:  # otherwise, it must be sorted
            assert last_key < key, f"Order is not respcted at {path} ({last_key} < {key})"

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

                validate(data, schema)
                assert_key_order(data)

            except Exception as e:
                raise ValueError(f"Fail to validate manifests/{file}") from e


if __name__ == "__main__":
    validate_manifest_files()
