from collections import defaultdict
import json
from jsonschema.exceptions import ValidationError
import os
import ast
import re
from pathlib import Path

from utils._decorators import CustomSpec as SemverRange
from utils.get_declaration import match_rule

from jsonschema import validate
import yaml
from semantic_version import Version


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


def sanitize_version(version: str) -> str:
    if re.fullmatch(r"(<|>|=)*[0-9]*\.[0-9]*\.[0-9]*(-|\+|\.|[a-z]|[A-Z]|[0-9])*", version.strip()):
        core_version = re.match(r"(<|>|=)*[0-9]*\.[0-9]*\.[0-9]", version)
        connector = ""
        if version[core_version.end() :] and not version[core_version.end() :].startswith(("-", ".", "+")):
            connector = "-"
        version = version[: core_version.end()] + connector + version[core_version.end() :].replace(".", "-")
    return version


def _load_file(file: str, component: str):
    def to_semver(version: str, nodeid: str):  # noqa: ARG001
        par = version.find("(")
        if par >= 0:
            version = version[:par]

        version = sanitize_version(version)

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
            value = {}  # noqa: PLW2901
            if sdec.startswith(("bug", "flaky", "incomplete_test_app", "irrelevant", "missing_feature")):
                value["declaration"] = sdec
            else:
                if sdec.startswith((">", "v")):
                    sdec = "<" + sdec[1:]
                elif not re.fullmatch("[0-9].*", sdec):
                    raise ValueError(f"Invalid inline version: {sdec}")
                value["library_version"] = to_semver(sdec, nodeid)
                value["declaration"] = "missing_feature"
        if not isinstance(value, list):
            value = [value]  # noqa: PLW2901
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


def assert_key_order(obj: dict, path: str = "") -> list[str]:
    last_key = "/"
    errors = []

    for key in obj:
        if not last_key < key:
            errors.append(f"Order is not respected at {path} ({last_key} < {key})")
        last_key = key

    return errors


def assert_nodeids_exist(obj: dict, path: str = "") -> list[str]:  # noqa: ARG001
    errors = []
    for key in obj:
        elements = key.split("::")

        if not Path(elements[0]).exists():
            errors.append(f"{elements[0]} does not exist")
            continue

        if len(elements) < 2 or ".py" not in elements[0]:  # noqa: PLR2004
            continue

        with open(elements[0]) as f:
            test_ast = ast.parse(f.read())

        found_class = False
        found_function = len(elements) < 3  # noqa: PLR2004
        for node in ast.walk(test_ast):
            if not isinstance(node, ast.ClassDef) or node.name != elements[1]:
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
        if found_class and not found_function and len(elements) >= 3:  # noqa: PLR2004
            errors.append(f"{elements[0]}::{elements[1]} does not contain function {elements[2]}")

    return errors


def assert_increasing_versions(obj: dict) -> list[str]:
    def to_version(sdec: str):
        if sdec.startswith(("bug", "flaky", "incomplete_test_app", "irrelevant", "missing_feature")):
            return None
        while len(sdec.split(".")) < 3:  # noqa: PLR2004
            sdec += ".0"
        sdec = sdec.strip("v")
        sdec = sdec[: sdec.find(" ") % (len(sdec) + 1)]
        sdec = sdec[: sdec.find("(") % (len(sdec) + 1)]
        sdec = sanitize_version(sdec)
        return Version(sdec.strip(">").strip("="))

    stack = []
    errors = []
    for key, val in obj.items():
        if not isinstance(val, str):
            continue

        while stack and not match_rule(stack[-1][0], key):
            stack.pop()

        version = to_version(val)
        if not version:
            continue

        if not stack:
            stack.append((key, version))
            continue

        if stack[-1][1] >= version:
            errors.append(f"{stack[-1][0]} version ({stack[-1][1]}) should be lower than {key} version ({version})")
        stack.append((key, val))

    return errors


def pretty(errors: dict[str, list]) -> str:
    ret = ""
    for file, file_errors in errors.items():
        ret += f"{file}:\n"
        for error in file_errors:
            ret += "\n".join("    " + line for line in str(error).splitlines()) + "\n"
    return ret


def validate_manifest_files() -> None:
    with open("manifests/parser/schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    order_errors = {}
    validation_errors = {}
    nodeid_errors = {}
    parser_errors = {}
    increasing_versions_errors = {}

    for file in os.listdir("manifests/"):
        if file.endswith(".yml"):
            with open(f"manifests/{file}", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            try:
                validate(data, schema)
            except ValidationError as e:
                validation_errors[file] = [e]

            errors = assert_key_order(data["manifest"])
            if errors:
                order_errors[file] = errors

            errors = assert_nodeids_exist(data["manifest"])
            if errors:
                nodeid_errors[file] = errors

            try:
                _load_file(f"manifests/{file}", file.strip(".yml"))
            except ValueError as e:
                parser_errors[file] = [e]

            errors = assert_increasing_versions(data["manifest"])
            if errors:
                increasing_versions_errors[file] = errors

    message = ""
    if order_errors:
        message += "\n====================Key order errors====================\n" + pretty(order_errors)
    if validation_errors:
        message += "\n================Syntax validation errors================\n" + pretty(validation_errors)
    if nodeid_errors:
        message += "\n=====================Node ID errors=====================\n" + pretty(nodeid_errors)
    if parser_errors:
        message += "\n===================Declaration errors===================\n" + pretty(parser_errors)
    if increasing_versions_errors:
        message += "\n==================Version order errors==================\n" + pretty(increasing_versions_errors)
    assert not message, message


if __name__ == "__main__":
    validate_manifest_files()
