import json
from jsonschema import validate
import yaml
from pathlib import Path
import ast
from typing import TYPE_CHECKING

from .parser import _load_file

if TYPE_CHECKING:
    from collections.abc import Callable


def assert_key_order(obj: dict, path: str = "") -> list[str]:
    obj = obj["manifest"]
    last_key = "/"
    errors = []

    for key in obj:
        if not last_key < key:
            errors.append(f"Order is not respected at {path} ({last_key} < {key})")
        last_key = key

    return errors


def _find_class_in_ast(module_ast: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Find a class definition by name in the AST."""
    for node in ast.iter_child_nodes(module_ast):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _function_exists_in_class(
    class_node: ast.ClassDef, function_name: str, module_ast: ast.Module
) -> bool:
    """Check if a function exists in a class, including inherited methods."""
    # Check direct methods first
    for child in ast.iter_child_nodes(class_node):
        if isinstance(child, ast.FunctionDef) and child.name == function_name:
            return True

    # Check inherited methods from base classes
    for base in class_node.bases:
        # Handle simple name references (e.g., "BaseClass")
        if isinstance(base, ast.Name):
            base_class = _find_class_in_ast(module_ast, base.id)
            if base_class and _function_exists_in_class(base_class, function_name, module_ast):
                return True
        # Handle attribute references (e.g., "module.BaseClass")
        elif isinstance(base, ast.Attribute):
            # For attribute references, try to resolve the name
            # This handles cases like "module.BaseClass" or "parent.BaseClass"
            if isinstance(base.value, ast.Name):
                base_class = _find_class_in_ast(module_ast, base.attr)
                if base_class and _function_exists_in_class(base_class, function_name, module_ast):
                    return True

    return False


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
        class_node = _find_class_in_ast(test_ast, elements[1])

        if class_node:
            found_class = True
            if len(elements) >= 3:  # noqa: PLR2004
                found_function = _function_exists_in_class(class_node, elements[2], test_ast)

        if not found_class:
            errors.append(f"{elements[0]} does not contain class {elements[1]}")
        if found_class and not found_function and len(elements) >= 3:  # noqa: PLR2004
            errors.append(f"{elements[0]}::{elements[1]} does not contain function {elements[2]}")

    return errors


# def assert_increasing_versions(obj: dict) -> list[str]:
#     obj = obj["manifest"]
#     stack = []
#     errors = []
#     for key, val in obj.items():
#         if not isinstance(val, str):
#             continue
#
#         while stack and not match_rule(stack[-1][0], key):
#             stack.pop()
#
#         declaration = Declaration(val, is_inline=True, semver_factory=lambda v: Version(v.strip("<").strip("=")))
#         if declaration.is_skip:
#             continue
#         version = declaration.value
#
#         if not stack:
#             stack.append((key, version))
#             continue
#
#         if stack[-1][1] >= version:
#             errors.append(f"{stack[-1][0]} version ({stack[-1][1]}) should be lower than {key} version ({version})")
#         stack.append((key, val))
#
#     return errors


def pretty(name: str, errors: dict[str, list]) -> str:
    width = 80
    padding = width - len(name)
    ret = "\n" + "=" * (padding // 2 + padding % 2) + name + "=" * (padding // 2) + "\n"
    for file, file_errors in errors.items():
        ret += f"{file}:\n"
        for error in file_errors:
            ret += "\n".join("    " + line for line in str(error).splitlines()) + "\n"
    return ret


def validate_manifest_files(path: Path = Path("manifests/")) -> None:
    with open("utils/manifest/schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    validations: list[tuple[str, Callable]] = [
        ("Syntax validation errors", lambda d: validate(d, schema) or []),
        ("Key order errors", assert_key_order),
        ("Node ID errors", assert_nodeids_exist),
        # ("Version order errors", assert_increasing_versions),
    ]

    all_errors: dict[str, dict[Path, list[BaseException]]] = {}

    for file in path.iterdir():
        if file.is_dir():
            continue
        if file.suffix == ".yml":
            with open(file, encoding="utf-8") as f:
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
                _load_file(file, file.stem)
            except Exception as e:
                name = "Loading errors"
                all_errors[name] = {}
                all_errors[name][file] = [e]

    message = ""
    for name, errors in all_errors.items():
        message += pretty(name, errors)

    assert not message, message


if __name__ == "__main__":
    validate_manifest_files()
