from collections import defaultdict
from functools import lru_cache
import json
from jsonschema.exceptions import ValidationError
import os
import ast
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

        return SemverRange(version)

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
                    value["declaration"] = "missing_feature"
            if not isinstance(value, list):
                value = [value]
            for entry in value:
                if isinstance(entry.get("library_version"), str):
                        entry["library_version"] = to_semver(entry["library_version"], nodeid)
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


def assert_key_order(obj: dict, path: str = ""):
    last_key = "/"
    errors = []

    for key in obj.keys():
        if not last_key < key:
            errors.append(f"Order is not respected at {path} ({last_key} < {key})")
        last_key = key

    return errors

def assert_nodeids_exist(obj: dict, path: str = ""):
    errors = []
    for key in obj.keys():
        elements = key.split("::")

        if not os.path.exists(elements[0]):
            errors.append(f"{elements[0]} does not exist")
            continue

        if len(elements) < 2 or not ".py" in elements[0]:
            continue

        with open(elements[0]) as f:
            test_ast = ast.parse(f.read())

        found_class = False
        found_function = len(elements) < 3
        for node in ast.walk(test_ast):
            if not isinstance(node, ast.ClassDef) or not node.name == elements[1]:
                continue
            if found_class:
                break

            found_class = True
            for child in ast.walk(node):
                if found_function:
                    break

                if isinstance(child, ast.FunctionDef) and child.name == elements[2]:
                    found_function = True

        if not found_class:
            errors.append(f"{elements[0]} does not contain class {elements[1]}")
        if found_class and not found_function and len(elements) >= 3:
            errors.append(f"{elements[0]}::{elements[1]} does not contain function {elements[2]}")

    return errors

def pretty(errors):
    ret = ""
    for file, file_errors in errors.items():
        ret += f"{file}:\n"
        for error in file_errors:
            ret += '\n'.join('    ' + line for line in str(error).splitlines()) + "\n"
    return ret



def validate_manifest_files() -> None:
    with open("manifests/parser/schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    order_errors = {}
    validation_errors = {}
    nodeid_errors = {}
    parser_errors = {}
    
    for file in os.listdir("manifests/"):
        if file.endswith(".yml"):
            with open(f"manifests/{file}", encoding="utf-8") as f:
                raw_data = f.read()
            with open(f"manifests/{file}", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            try:
                validate(data, schema)
            except ValidationError as e:
                validation_errors[file] = [e]

            errors = assert_key_order(data["manifest"])
            if errors: order_errors[file] = errors

            errors = assert_nodeids_exist(data["manifest"])
            if errors: nodeid_errors[file] = errors

            try:
                _load_file(f"manifests/{file}", file.strip(".yml"))
            except ValueError as e:
                parser_errors[file] = [e]

    message = ""
    if order_errors:
        message += "\n====================Key order errors====================\n" + pretty(order_errors)
    if validation_errors:
        message += "\n================Syntax validation errors================\n" + pretty(validation_errors)
    if nodeid_errors:
        message += "\n=====================Node ID errors=====================\n" + pretty(nodeid_errors)
    if parser_errors:
        message += "\n===================Declaration errors===================\n" + pretty(parser_errors)
    assert not message, message

if __name__ == "__main__":
    validate_manifest_files()
