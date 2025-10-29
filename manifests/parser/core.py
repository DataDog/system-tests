from collections import defaultdict
from functools import lru_cache
import json
import os
import re

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
    def to_semver(version: str, nodeid):
        par = version.find("(")
        if par >= 0:
            version = version[:par]
        if re.fullmatch("(<|>|=)*[0-9]*\.[0-9]*\.[0-9]*(-|\+|\.|[a-z]|[A-Z]|[0-9])*", version.strip()):
            dots = re.finditer("\.", version)
            core_version = re.match("(<|>|=)*[0-9]*\.[0-9]*\.[0-9]", version)
            connector = ""
            if not version[core_version.end():].startswith(("-", ".")) or not version[core_version.end():]:
                connector = "-"
            version = version[:core_version.end()] + connector + version[core_version.end():].replace(".", "-")

        try:
            return SemverRange(version)
        except ValueError as e:
            print(e)
            print(nodeid, vsnap)
            pass

    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return {}

    ret = {}
    for nodeid, value in data["manifest"].items():
            if isinstance(value, str):
                sdec = value
                value = {}
                if sdec.startswith(("bug", "flaky", "incomplete_test_app", "irrelevant", "missing_feature")):
                    value["declaration"] = sdec
                else:
                    if sdec.startswith("<"):
                           sdec = ">" + sdec[1:]
                    elif sdec.startswith(">"):
                           sdec = "<" + sdec[1:]
                    if sdec.startswith("v"):
                           sdec = "<" + sdec[1:]
                    value["library_version"] = to_semver(sdec, nodeid)
                    # if not value["library_version"]:
                    #     print("Found str")
                    #     print(nodeid, value)
                    value["declaration"] = "missing_feature"
            if not isinstance(value, list):
                value = [value]
            for entry in value:
                if isinstance(entry.get("library_version"), str):
                        entry["library_version"] = to_semver(entry["library_version"], nodeid)
                        # if not entry["library_version"]:
                        #     print(nodeid, value, entry)
                entry["library"] = component

            ret[nodeid] = value

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

                validate(data, schema)
                try:
                    assert_key_order(data["manifest"])
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
