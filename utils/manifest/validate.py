import json
from semantic_version import Version
from jsonschema import validate
import yaml
import os
from pathlib import Path
from utils.manifest.declaration import Declaration
from utils.manifest.rule import match_rule
import ast
from utils.manifest.parser import _load_file

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


def validate_manifest_files(path: str= "manifests/") -> None:
    with open("utils/manifest/schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    validations = [
        ("Syntax validation errors", lambda d: validate(d, schema)),
        ("Key order errors", assert_key_order),
        ("Node ID errors", assert_nodeids_exist),
        # ("Version order errors", assert_increasing_versions),
    ]

    all_errors = {}

    for file in os.listdir(path):
        if file.endswith(".yml"):
            with open(f"{path}/{file}", encoding="utf-8") as f:
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
                _load_file(f"{path}/{file}", file.strip(".yml"))
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
