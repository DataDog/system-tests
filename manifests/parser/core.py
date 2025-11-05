import ast
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import yaml
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from semantic_version import Version

from utils._decorators import CustomSpec as SemverRange
from utils.get_declaration import match_rule


class Declaration:
    skip_declaration_regex = r"(bug|flaky|incomplete_test_app|irrelevant|missing_feature) ?\(?(.*)\)?"
    version_regex = r"(?:\d+\.\d+\.\d+|\d+\.\d+|\d+)[.+-]?[.\w+-]*"
    simple_regex = rf"(>|>=|v)?({version_regex}) ?\(?(.*)\)?"
    full_regex = r"([^()]*) ?\(?(.*)\)?"

    def __init__(self, raw_declaration: str, is_inline: bool = False, semver_factory = SemverRange):
        if not raw_declaration:
            raise ValueError("raw_declaration must not be None or an empty string")
        self.raw = raw_declaration.strip()
        self.is_inline = is_inline
        self.semver_factory = semver_factory
        self.parse_declaration()

    @staticmethod
    def fix_separator(version: str):
        elements = re.fullmatch(r"(\d+\.\d+\.\d+)([.+-]?)([.\w+-]*)", version)
        if not elements or not elements.group(3):
            return version
        if not elements.group(2) or elements.group(2) == ".":
            sanitized_version = elements.group(1) + "-" + elements.group(3)
        else:
            sanitized_version = elements.group(1) + elements.group(2) + elements.group(3)
        return sanitized_version

    @staticmethod
    def fix_missing_minor_patch(version: str):
        elements = re.fullmatch(r"(\d+\.\d+\.\d+|\d+\.\d+|\d+)(.*)", version)
        while not re.fullmatch(r"\d+\.\d+\.\d+.*", version):
            version += ".0"
        return version

    transformations = [fix_separator, fix_missing_minor_patch]

    @staticmethod
    def sanitize_version(version: str, transformations=transformations):
        matches = re.finditer(Declaration.version_regex, version)
        sanitized = []
        for match in matches:
            matched_section = version[match.start():match.end()]
            for transformation in transformations:
                matched_section = transformation(matched_section)
            version = f"{version[:match.start()]}{matched_section}{version[match.end():]}"
        return version

    def parse_declaration(self):
        elements = re.fullmatch(self.skip_declaration_regex, self.raw, re.A)
        if elements:
            self.is_skip = True
            self.declaration = elements[0]
            if elements[1]:
                self.reason = elements[1]
            return

        if self.is_inline:
            elements = re.fullmatch(self.simple_regex, self.raw, re.A)
        else:
            elements = re.fullmatch(self.full_regex, self.raw, re.A)

        if not elements:
            raise ValueError(f"Wrong version format: {self.raw} (is inline: {self.is_inline})")

        self.is_skip = False
        if self.is_inline:
            if elements.group(1) == ">":
                sanitized_version = f"<={Declaration.sanitize_version(elements.group(2))}"
            else:
                sanitized_version = f"<{Declaration.sanitize_version(elements.group(2))}"
        else:
            sanitized_version = Declaration.sanitize_version(elements.group(1))

        self.declaration = self.semver_factory(sanitized_version)
        if elements.group(len(elements.groups()) - 1):
            self.reason = elements.group(len(elements.groups()) - 1)

    def __str__(self):
        if self.reason:
            return f"{self.declaration} ({self.reason})"
        else:
            return f"{self.declaration}"


def _load_file(file: str, component: str):
    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return {}

    ret = {}
    for nodeid, value in data["manifest"].items():
        if isinstance(value, str):
            declaration = Declaration(value, is_inline=True)
            value = {}  # noqa: PLW2901
            if declaration.is_skip:
                value["declaration"] = str(declaration)
            else:
                value["library_version"] = declaration.declaration
                value["declaration"] = "missing_feature"
        if not isinstance(value, list):
            value = [value]  # noqa: PLW2901
        for entry in value:
            if isinstance(entry.get("library_version"), str):
                entry["library_version"] = Declaration(entry["library_version"]).declaration
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
    stack = []
    errors = []
    for key, val in obj.items():
        if not isinstance(val, str):
            continue

        while stack and not match_rule(stack[-1][0], key):
            stack.pop()

        declaration = Declaration(val, is_inline=True, semver_factory=lambda v: Version(v.strip("<").strip("=")))
        if declaration.is_skip:
            continue
        version = declaration.declaration

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
