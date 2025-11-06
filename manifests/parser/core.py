import ast
import json
import os
import re
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

import yaml
from jsonschema import validate
from semantic_version import Version

from utils._decorators import CustomSpec as SemverRange
from utils.get_declaration import match_rule


class Declaration:
    reason_regex = r" ?(?:\((.*)\))?"
    skip_declaration_regex = fr"(bug|flaky|incomplete_test_app|irrelevant|missing_feature){reason_regex}"
    version_regex = r"(?:\d+\.\d+\.\d+|\d+\.\d+|\d+)[.+-]?[.\w+-]*"
    simple_regex = rf"(>|>=|v)?({version_regex}){reason_regex}"
    full_regex = rf"([^()]*){reason_regex}"

    def __init__(
        self, raw_declaration: str, *, is_inline: bool = False, semver_factory: type[SemverRange] = SemverRange
    ) -> None:
        if not raw_declaration:
            raise ValueError("raw_declaration must not be None or an empty string")
        self.raw = raw_declaration.strip()
        self.is_inline = is_inline
        self.semver_factory = semver_factory
        self.parse_declaration()

    @staticmethod
    def fix_separator(version: str) -> str:
        elements = re.fullmatch(r"(\d+\.\d+\.\d+)([.+-]?)([.\w+-]*)", version)
        if not elements or not elements.group(3):
            return version
        if not elements.group(2) or elements.group(2) == ".":
            sanitized_version = elements.group(1) + "-" + elements.group(3)
        else:
            sanitized_version = elements.group(1) + elements.group(2) + elements.group(3)
        return sanitized_version

    @staticmethod
    def fix_missing_minor_patch(version: str) -> str:
        for _ in range(2):
            if re.fullmatch(r"\d+\.\d+\.\d+.*", version):
                break
            version += ".0"
        return version

    transformations = [fix_separator, fix_missing_minor_patch]

    @staticmethod
    def sanitize_version(version: str, transformations: list[Callable[[str], str]] | None = None) -> str:
        if transformations is None:
            transformations = Declaration.transformations
        matches = re.finditer(Declaration.version_regex, version)
        for match in matches:
            matched_section = version[match.start() : match.end()]
            for transformation in transformations:
                matched_section = transformation(matched_section)
            version = f"{version[:match.start()]}{matched_section}{version[match.end():]}"
        return version

    def parse_declaration(self) -> None:
        elements = re.fullmatch(self.skip_declaration_regex, self.raw, re.ASCII)
        if elements:
            self.is_skip = True
            self.value = elements[1]
            if elements[1]:
                self.reason = elements[2]
            return

        if self.is_inline:
            elements = re.fullmatch(self.simple_regex, self.raw, re.ASCII)
        else:
            elements = re.fullmatch(self.full_regex, self.raw, re.ASCII)

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

        self.value = self.semver_factory(sanitized_version)
        if elements.group(len(elements.groups()) - 1):
            self.reason = elements.group(len(elements.groups()) - 1)

    def __str__(self):
        if self.reason:
            return f"{self.value} ({self.reason})"
        return f"{self.value}"


def _load_file(file: str, component: str):
    try:
        with open(file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return {}

    ret = {}
    for nodeid, raw_value in data["manifest"].items():
        if isinstance(raw_value, str):
            declaration = Declaration(raw_value, is_inline=True)
            value = {}
            if declaration.is_skip:
                value["declaration"] = str(declaration)
            else:
                value["library_version"] = declaration.value
                value["declaration"] = "missing_feature"
            value["library"] = component
            value = [value]
        else:
            value = raw_value
            if not isinstance(raw_value, list):
                value = [raw_value]
            for entry in value:
                if "library_version" in entry:
                    entry["library_version"] = Declaration(entry["library_version"]).value
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
    obj = obj["manifest"]
    last_key = "/"
    errors = []

    for key in obj:
        if not last_key < key:
            errors.append(f"Order is not respected at {path} ({last_key} < {key})")
        last_key = key

    return errors


def assert_nodeids_exist(obj: dict) -> list[str]:
    obj = obj["manifest"]
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
        for node in ast.iter_child_nodes(test_ast):
            if not isinstance(node, ast.ClassDef) or node.name != elements[1]:
                continue
            if found_class:
                break

            found_class = True
            for child in ast.iter_child_nodes(node):
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
    obj = obj["manifest"]
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
        version = declaration.value

        if not stack:
            stack.append((key, version))
            continue

        if stack[-1][1] >= version:
            errors.append(f"{stack[-1][0]} version ({stack[-1][1]}) should be lower than {key} version ({version})")
        stack.append((key, val))

    return errors


def pretty(name: str, errors: dict[str, list]) -> str:
    width = 80
    padding = width - len(name)
    ret = "\n" + "=" * (padding // 2 + padding % 2) + name + "=" * (padding // 2) + "\n"
    for file, file_errors in errors.items():
        ret += f"{file}:\n"
        for error in file_errors:
            ret += "\n".join("    " + line for line in str(error).splitlines()) + "\n"
    return ret


def validate_manifest_files() -> None:
    with open("manifests/parser/schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    validations = [
        ("Syntax validation errors", lambda d: validate(d, schema)),
        ("Key order errors", assert_key_order),
        ("Node ID errors", assert_nodeids_exist),
        ("Version order errors", assert_increasing_versions),
    ]

    all_errors = {}

    for file in os.listdir("manifests/"):
        if file.endswith(".yml"):
            with open(f"manifests/{file}", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            for name, validation in validations:
                try:
                    errors = validation(data)
                except BaseException as e:
                    errors = [e]
                if errors:
                    if name not in all_errors:
                        all_errors[name] = {}
                    all_errors[name][file] = errors

            try:
                _load_file(f"manifests/{file}", file.strip(".yml"))
            except BaseException as e:
                name = "Loading errors"
                all_errors[name] = {}
                all_errors[name][file] = [e]

    message = ""
    for name, errors in all_errors.items():
        message += pretty(name, errors)

    assert not message, message


if __name__ == "__main__":
    validate_manifest_files()
