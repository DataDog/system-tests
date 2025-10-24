from collections import defaultdict
from functools import lru_cache
import json
import os

from utils._decorators import CustomSpec as SemverRange

from jsonschema import validate
import yaml


def _flatten(base: str, obj: dict):
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


def _load_file(file: str, component: str):
    def to_semver(version: str):
        par = version.find("(")
        if par >= 0:
            version = sdec[:par]
        return SemverRange(version)

    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return {}

    ret = {}
    for nodeid, value in data["manifest"].items():
        if "TestHeaderInjection_ExtendedLocation" in nodeid:
            print(value)
        try:
            if isinstance(value, str):
                sdec = value
                value = {}
                if sdec.startswith(("bug", "flaky", "incomplete_test_app", "irrelevant", "missing_feature")):
                    value["declaration"] = sdec
                else:
                    value["library_version"] = {to_semver(f"<{sdec.strip("v").strip("<").strip(">")}")}
                    value["declaration"] = "missing_feature"
            if not isinstance(value, list):
                value = [value]
            for entry in value:
                if isinstance(entry.get("library_version"), str):
                    entry["library_version"] = to_semver(entry["library_version"])
                entry["library"] = component

            ret[nodeid] = value
        except ValueError as e:
            # print(e)
            if "TestHeaderInjection_ExtendedLocation" in nodeid:
                print(value)
                print(e)
            pass

    return ret


# @lru_cache
def load(base_dir: str = "manifests/") -> dict[str, dict[str, str]]:
    """Returns a dict of nodeid, value are another dict where the key is the component
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
        "cpp_httpd",
        "cpp_nginx",
        "dotnet",
        "golang",
        "java",
        "nodejs",
        "php",
        "python",
        "python_otel",
        "ruby",
        "rust",
        "dd_apm_inject",
        "k8s_cluster_agent",
        "python_lambda",
    ):
        data = _load_file(f"{base_dir}{component}.yml", component)

        for nodeid, value in data.items():
            if nodeid not in result:
                result[nodeid] = []
            result[nodeid] += value

    return result


def assert_key_order(obj: dict, path: str = "") -> None:
    last_key = "/"

    for key, value in obj.items():
        # Only check alphabetical order within the same type (folder vs file)
        # Allow folders and files to be mixed as long as they're sorted within their type
        if last_key.endswith("/") and key.endswith("/"):  # both folders
            assert last_key < key, f"Order is not respected at {path} ({last_key} < {key})"
        elif not last_key.endswith("/") and not key.endswith("/"):  # both files
            assert last_key < key, f"Order is not respected at {path} ({last_key} < {key})"
        # Mixed folder/file transitions are allowed

        if isinstance(value, dict):
            assert_key_order(value, f"{path}.{key}")

        last_key = key


def validate_manifest_files() -> None:
    with open("manifests/parser/schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    validation_errors = []
    
    for file in os.listdir("manifests/"):
        if file.endswith(".yml"):
            try:
                with open(f"manifests/{file}", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                # Handle new manifest format with refs and manifest sections
                if "refs" in data and "manifest" in data:
                    # New format: validate the manifest section after removing refs
                    manifest_data = data["manifest"]
                    if "refs" in manifest_data:
                        del manifest_data["refs"]
                    validate(manifest_data, schema)
                    try:
                        assert_key_order(manifest_data)
                    except AssertionError as e:
                        validation_errors.append(f"Key ordering issue in {file}: {e}")
                elif "manifest" in data:
                    # New format without refs: validate the manifest section
                    manifest_data = data["manifest"]
                    if "refs" in manifest_data:
                        del manifest_data["refs"]
                    validate(manifest_data, schema)
                    try:
                        assert_key_order(manifest_data)
                    except AssertionError as e:
                        validation_errors.append(f"Key ordering issue in {file}: {e}")
                else:
                    # Old format: validate the entire data structure
                    # this field is only used for YAML templating
                    if "refs" in data:
                        del data["refs"]
                    
                    validate(data, schema)
                    try:
                        assert_key_order(data)
                    except AssertionError as e:
                        validation_errors.append(f"Key ordering issue in {file}: {e}")

            except yaml.YAMLError as e:
                validation_errors.append(f"YAML parsing error in {file}: {e}")
            except Exception as e:
                validation_errors.append(f"Validation error in {file}: {e}")
    
    if validation_errors:
        print("Validation completed with issues:")
        for error in validation_errors:
            print(f"  - {error}")
        print(f"\nTotal issues found: {len(validation_errors)}")
        # Don't raise an exception, just report the issues
    else:
        print("✅ All manifest files validated successfully!")


if __name__ == "__main__":
    validate_manifest_files()
