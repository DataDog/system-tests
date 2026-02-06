import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from jsonschema import validate

from utils._context.core import context

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


class _MockScenario:
    """Minimal mock scenario for manifest validation imports."""

    collect_only = True
    components: dict = {}
    parametrized_tests_metadata = None


def _setup_mock_context() -> object | None:
    """Set up a mock context.scenario to allow test file imports.

    Returns the original scenario (if any) so it can be restored later.
    """
    original_scenario = getattr(context, "scenario", None)
    context.scenario = _MockScenario()  # type: ignore[assignment]
    return original_scenario


def _restore_context(original_scenario: object | None) -> None:
    """Restore the original context.scenario."""
    if original_scenario is not None:
        context.scenario = original_scenario  # type: ignore[assignment]
    elif hasattr(context, "scenario"):
        delattr(context, "scenario")


def _import_module_from_path(file_path: str) -> object | None:
    """Dynamically import a module from a file path."""
    path = Path(file_path)
    module_name = path.stem

    # Create a unique module name to avoid conflicts
    unique_module_name = f"_manifest_check_{module_name}_{hash(file_path)}"

    # Determine the package path for relative imports (e.g., "tests.parametric")
    package_path = ".".join(path.parent.parts)

    spec = importlib.util.spec_from_file_location(
        unique_module_name, file_path, submodule_search_locations=[str(path.parent)]
    )
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    module.__package__ = package_path
    sys.modules[unique_module_name] = module

    # Set up mock context to allow imports of test files
    original_scenario = _setup_mock_context()

    try:
        spec.loader.exec_module(module)
    except Exception:
        # If the module fails to load, return None
        if unique_module_name in sys.modules:
            del sys.modules[unique_module_name]
        return None
    finally:
        _restore_context(original_scenario)

    return module


def _find_class_in_ast(module_ast: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Find a class definition by name in the AST."""
    for node in ast.iter_child_nodes(module_ast):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _function_exists_in_class(class_node: ast.ClassDef, function_name: str, module_ast: ast.Module) -> bool:
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


def _check_with_ast(file_path: str, class_name: str, function_name: str | None) -> tuple[bool, bool]:
    """Check class/function existence using AST parsing. Returns (found_class, found_function)."""
    with open(file_path, encoding="utf-8") as f:
        test_ast = ast.parse(f.read())

    class_node = _find_class_in_ast(test_ast, class_name)
    found_class = class_node is not None
    found_function = function_name is None  # If no function to check, consider it found

    if found_class and function_name is not None and class_node is not None:
        found_function = _function_exists_in_class(class_node, function_name, test_ast)

    return found_class, found_function


def assert_nodeids_exist(obj: dict) -> list[str]:
    obj = obj["manifest"]
    errors = []
    module_cache: dict[str, object | None] = {}

    for key in obj:
        elements = key.split("::")

        if not Path(elements[0]).exists():
            errors.append(f"{elements[0]} does not exist")
            continue

        if len(elements) < 2 or ".py" not in elements[0]:  # noqa: PLR2004
            continue

        file_path = elements[0]
        class_name = elements[1]
        function_name = elements[2] if len(elements) >= 3 else None  # noqa: PLR2004

        # Try to import the module and use hasattr
        if file_path not in module_cache:
            module_cache[file_path] = _import_module_from_path(file_path)

        module = module_cache[file_path]

        if module is not None:
            # Use hasattr for validation
            found_class = hasattr(module, class_name)

            if not found_class:
                errors.append(f"{file_path} does not contain class {class_name}")
                continue

            if function_name is not None:
                class_obj = getattr(module, class_name)
                found_function = hasattr(class_obj, function_name)

                if not found_function:
                    errors.append(f"{file_path}::{class_name} does not contain function {function_name}")
        else:
            # Fall back to AST parsing if import fails
            # print("AST fallback: ", file_path)
            found_class, found_function = _check_with_ast(file_path, class_name, function_name)

            if not found_class:
                errors.append(f"{file_path} does not contain class {class_name}")
            elif not found_function:
                errors.append(f"{file_path}::{class_name} does not contain function {function_name}")

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


def validate_manifest_files(path: Path = Path("manifests/"), *, assume_sorted: bool = False) -> None:
    with open("utils/manifest/schema.json", encoding="utf-8") as f:
        schema = json.load(f)

    validations: list[tuple[str, Callable]] = [
        ("Syntax validation errors", lambda d: validate(d, schema) or []),
        ("Node ID errors", assert_nodeids_exist),
        # ("Version order errors", assert_increasing_versions),
    ]

    if not assume_sorted:
        validations.append(("Key order errors", assert_key_order))

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
