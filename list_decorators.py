#!/usr/bin/env python3
"""Script to list all decorators (bug, flaky, incomplete_test_app, irrelevant, missing_feature)
in the tests directory using Python AST parsing.

Usage:
    python list_decorators.py                    # Print all decorators
    python list_decorators.py --json             # Output as JSON
    python list_decorators.py --decorator bug    # Filter by decorator type
    python list_decorators.py --summary          # Show only summary counts
    python list_decorators.py --simple           # Show only simple decorators
    python list_decorators.py --complex          # Show only complex decorators
    python list_decorators.py --show-rejected    # Show rejected decorators when filtering

A decorator is considered "simple" if:
  - Its condition depends only on a single library (and optionally library version)
  - It does NOT have force_skip=True argument
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

# Import manifest utilities from utils/manifest
try:
    from utils.manifest import Manifest, ManifestData, SkipDeclaration, TestDeclaration
    from utils.manifest._internal.const import default_manifests_path
    from utils.manifest._internal.rule import match_rule
    from utils.manifest._internal.declaration import Declaration, _parse_skip_declaration
    from utils._context.component_version import ComponentVersion

    MANIFEST_UTILS_AVAILABLE = True
except ImportError:
    MANIFEST_UTILS_AVAILABLE = False
    default_manifests_path = Path("manifests/")
    ComponentVersion = None  # type: ignore[misc, assignment]

    # Fallback match_rule implementation if utils not available
    def match_rule(rule: str, nodeid: str) -> bool:
        """Fallback implementation of match_rule."""
        rule_elements = rule.strip("/").replace("::", "/").split("/")
        nodeid = nodeid.split("[")[0]
        nodeid_elements = nodeid.replace("::", "/").split("/")
        if len(rule_elements) > len(nodeid_elements):
            return False
        return nodeid_elements[: len(rule_elements)] == rule_elements


# Use TestDeclaration values for target decorators
TARGET_DECORATORS = frozenset({"bug", "flaky", "incomplete_test_app", "irrelevant", "missing_feature"})

# Pattern to match single library conditions like:
# context.library == "java", context.library < "python@2.5.0", context.library.name == "java"
SINGLE_LIBRARY_PATTERN = re.compile(
    r"^context\.library(?:\.name|\.version)?\s*(?:==|!=|<|>|<=|>=)\s*['\"][a-z_]+(?:@[\d.]+)?['\"]$"
)

# Valid library names
VALID_LIBRARIES = frozenset(
    {
        "cpp",
        "cpp_httpd",
        "cpp_nginx",
        "dotnet",
        "golang",
        "java",
        "nodejs",
        "python",
        "php",
        "ruby",
        "java_otel",
        "python_otel",
        "nodejs_otel",
        "python_lambda",
        "rust",
    }
)


def get_decorator_name(decorator: ast.expr) -> str | None:
    """Extract the decorator name from an AST node."""
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Call):
        if isinstance(decorator.func, ast.Name):
            return decorator.func.id
        if isinstance(decorator.func, ast.Attribute):
            return decorator.func.attr
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    return None


def ast_to_source(node: ast.expr) -> str:
    """Convert an AST node back to source code representation."""
    try:
        return ast.unparse(node)
    except Exception:
        return repr(node)


def extract_decorator_args(decorator: ast.expr) -> str:
    """Extract arguments from a decorator call."""
    if isinstance(decorator, ast.Call):
        args_parts: list[str] = []

        # Positional arguments
        for arg in decorator.args:
            args_parts.append(ast_to_source(arg))

        # Keyword arguments
        for kw in decorator.keywords:
            if kw.arg:
                args_parts.append(f"{kw.arg}={ast_to_source(kw.value)}")
            else:
                # **kwargs case
                args_parts.append(f"**{ast_to_source(kw.value)}")

        return ", ".join(args_parts)
    return ""


def extract_decorator_args_dict(decorator: ast.expr) -> dict[str, Any]:
    """Extract arguments from a decorator call as a dictionary."""
    result: dict[str, Any] = {"positional": [], "keyword": {}}
    if isinstance(decorator, ast.Call):
        # Positional arguments
        for arg in decorator.args:
            result["positional"].append(ast_to_source(arg))

        # Keyword arguments
        for kw in decorator.keywords:
            if kw.arg:
                result["keyword"][kw.arg] = ast_to_source(kw.value)

    return result


def collect_attribute_names(node: ast.expr) -> set[str]:
    """Collect all attribute access patterns like 'context.library', 'context.weblog_variant'."""
    names: set[str] = set()

    class AttributeCollector(ast.NodeVisitor):
        def visit_Attribute(self, attr_node: ast.Attribute) -> None:
            # Build the full attribute path (e.g., context.library.version)
            parts: list[str] = [attr_node.attr]
            current = attr_node.value
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            parts.reverse()
            names.add(".".join(parts))
            self.generic_visit(attr_node)

    AttributeCollector().visit(node)
    return names


def parse_library_version_from_string(version_string: str) -> tuple[str | None, str | None]:
    """Parse a library@version string using ComponentVersion.

    Args:
        version_string: String like 'golang@2.1.0-dev' or 'java'

    Returns:
        Tuple of (library_name, version_str) or (library_name, None) if no version

    """
    version_string = version_string.strip().strip("'\"")

    if "@" in version_string:
        if ComponentVersion is not None:
            try:
                cv = ComponentVersion(version_string.split("@")[0], version_string.split("@")[1])
                return cv.name, str(cv.version)
            except (ValueError, IndexError):
                pass
        # Fallback: simple split
        parts = version_string.split("@", 1)
        return parts[0], parts[1] if len(parts) > 1 else None

    return version_string, None


def count_libraries_in_condition(condition_str: str) -> int:
    """Count how many different libraries are mentioned in a condition string."""
    # Extract all quoted strings that look like library references
    quoted_strings = re.findall(r"['\"]([a-z_]+(?:@[^'\"]+)?)['\"]", condition_str)

    libraries_found: set[str] = set()
    for qs in quoted_strings:
        lib_name, _ = parse_library_version_from_string(qs)
        if lib_name and lib_name in VALID_LIBRARIES:
            libraries_found.add(lib_name)

    return len(libraries_found)


def analyze_decorator_simplicity(decorator: ast.expr) -> tuple[bool, str]:
    """Analyze if a decorator is "simple".

    A decorator is simple if:
    - Its condition depends only on a single library (and optionally library version)
    - It does NOT have force_skip=True argument

    Returns: (is_simple, rejection_reason)
    """
    if not isinstance(decorator, ast.Call):
        return False, "Not a function call"

    # Check for force_skip=True
    for kw in decorator.keywords:
        if kw.arg == "force_skip":
            if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                return False, "Has force_skip=True"

    # Check if using simple library= keyword argument
    has_library_kwarg = False
    has_condition_kwarg = False
    has_weblog_variant_kwarg = False
    condition_value: ast.expr | None = None

    for kw in decorator.keywords:
        if kw.arg == "library":
            has_library_kwarg = True
            # Check if it's a single library string
            if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                if kw.value.value in VALID_LIBRARIES:
                    # Simple case: library="java"
                    pass
                else:
                    return False, f"Unknown library: {kw.value.value}"
            else:
                return False, "Library argument is not a simple string"
        elif kw.arg == "condition":
            has_condition_kwarg = True
            condition_value = kw.value
        elif kw.arg == "weblog_variant":
            has_weblog_variant_kwarg = True

    # If weblog_variant is specified, it's not simple (depends on more than just library)
    if has_weblog_variant_kwarg:
        return False, "Has weblog_variant argument"

    # If library= keyword is used (and no other complex conditions), it's simple
    if has_library_kwarg and not has_condition_kwarg:
        return True, ""

    # Check positional argument (condition) or condition= keyword
    condition_expr: ast.expr | None = None
    if decorator.args:
        condition_expr = decorator.args[0]
    elif condition_value is not None:
        condition_expr = condition_value

    if condition_expr is None:
        # No condition specified - could be simple if library= is used
        if has_library_kwarg:
            return True, ""
        return False, "No condition or library specified"

    # Analyze the condition expression
    condition_str = ast_to_source(condition_expr)

    # Check for simple True/False constants
    if isinstance(condition_expr, ast.Constant):
        if condition_expr.value is True:
            return False, "Condition is always True (not library-specific)"
        if condition_expr.value is False:
            return False, "Condition is always False (not library-specific)"

    # Collect all context attributes used in the condition
    attributes = collect_attribute_names(condition_expr)

    # Filter to context.* attributes
    context_attrs = {a for a in attributes if a.startswith("context.")}

    # Check what context attributes are used
    allowed_library_attrs = {"context.library", "context.library.name", "context.library.version"}
    non_library_attrs = context_attrs - allowed_library_attrs

    if non_library_attrs:
        # Uses attributes other than context.library
        return False, f"Uses non-library attributes: {', '.join(sorted(non_library_attrs))}"

    # Check for 'or' operator - makes conditions complex
    if " or " in condition_str.lower():
        return False, "Condition uses 'or' operator"

    # Check for '!=' operator - affects multiple libraries (all except specified)
    if "!=" in condition_str:
        return False, "Condition uses '!=' operator (affects multiple libraries)"

    # Check for 'not in' operator - affects multiple libraries
    if " not in " in condition_str:
        return False, "Condition uses 'not in' operator (affects multiple libraries)"

    # Check if condition involves multiple libraries
    lib_count = count_libraries_in_condition(condition_str)
    if lib_count > 1:
        return False, f"Condition involves {lib_count} libraries"

    # Check for 'in' operator with multiple values (e.g., context.library in ['java', 'python'])
    if " in " in condition_str:
        # Check if it's a list/tuple with multiple items
        if re.search(r"\[.*,.*\]|\(.*,.*\)", condition_str):
            return False, "Condition uses 'in' with multiple values"

    # If we have library attributes and only one library, it's simple
    if context_attrs and lib_count == 1:
        return True, ""

    # If we have library attributes but no specific library mentioned, check if it's a version comparison
    if context_attrs and lib_count == 0:
        # Could be something like context.library.version.prerelease is not None
        return False, "Condition references library but doesn't specify which one"

    return False, f"Could not determine simplicity: {condition_str}"


def get_nodeid(filepath: Path, class_name: str | None, method_name: str | None, tests_dir: Path) -> str:
    """Generate pytest nodeid from filepath and class/method names."""
    try:
        rel_path = filepath.relative_to(tests_dir.parent)
    except ValueError:
        rel_path = filepath

    parts = [str(rel_path)]
    if class_name:
        parts.append(class_name)
    if method_name:
        parts.append(method_name)

    return "::".join(parts)


def extract_decorators_from_file(filepath: Path, tests_dir: Path) -> list[dict[str, Any]]:
    """Extract target decorators from a Python file using AST."""
    results: list[dict[str, Any]] = []

    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError) as e:
        sys.stderr.write(f"Warning: Could not parse {filepath}: {e}\n")
        return results

    def add_decorator_result(decorator: ast.expr, class_name: str | None, method_name: str | None) -> None:
        dec_name = get_decorator_name(decorator)
        if dec_name in TARGET_DECORATORS:
            is_simple, rejection_reason = analyze_decorator_simplicity(decorator)
            results.append(
                {
                    "decorator": dec_name,
                    "args": extract_decorator_args(decorator),
                    "args_dict": extract_decorator_args_dict(decorator),
                    "nodeid": get_nodeid(filepath, class_name, method_name, tests_dir),
                    "file": str(filepath.relative_to(tests_dir.parent)),
                    "line": decorator.lineno,
                    "is_simple": is_simple,
                    "rejection_reason": rejection_reason,
                }
            )

    for node in ast.walk(tree):
        # Check class definitions
        if isinstance(node, ast.ClassDef):
            for decorator in node.decorator_list:
                add_decorator_result(decorator, node.name, None)

            # Check methods within the class
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    for decorator in item.decorator_list:
                        add_decorator_result(decorator, node.name, item.name)

        # Check top-level functions
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Skip if it's inside a class (already handled above)
            parent_is_module = True
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    for child in parent.body:
                        if child is node:
                            parent_is_module = False
                            break

            if parent_is_module:
                for decorator in node.decorator_list:
                    add_decorator_result(decorator, None, node.name)

    return results


def find_python_files(
    tests_dir: Path,
    exclude_dirs: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[Path]:
    """Find all Python test files in the tests directory.

    Args:
        tests_dir: Root directory to search
        exclude_dirs: List of directory names to exclude (e.g., ['test', 'fixtures'])
        exclude_patterns: List of glob patterns to exclude files (e.g., ['**/test_otel*.py'])

    Returns:
        List of Python file paths, sorted

    """
    import fnmatch

    exclude_set = set(exclude_dirs) if exclude_dirs else set()
    files: list[Path] = []

    for py_file in tests_dir.rglob("*.py"):
        # Check if any parent directory should be excluded
        should_exclude = False
        for parent in py_file.parents:
            if parent.name in exclude_set:
                should_exclude = True
                break

        # Check if file matches any exclude pattern
        if not should_exclude and exclude_patterns:
            file_str = str(py_file)
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(file_str, pattern) or fnmatch.fnmatch(py_file.name, pattern):
                    should_exclude = True
                    break

        if not should_exclude:
            files.append(py_file)

    return sorted(files)


# =============================================================================
# Manifest Entry Generation
# =============================================================================


def extract_library_from_condition(condition_str: str) -> str | None:
    """Extract the library name from a condition string.

    Examples:
        "context.library == 'java'" -> "java"
        "context.library < 'python@2.5.0'" -> "python"
        "context.library != 'golang'" -> "golang"

    """
    # Extract quoted strings that look like library references
    quoted_strings = re.findall(r"['\"]([a-z_]+(?:@[^'\"]+)?)['\"]", condition_str)

    for qs in quoted_strings:
        lib_name, _ = parse_library_version_from_string(qs)
        if lib_name and lib_name in VALID_LIBRARIES:
            return lib_name

    return None


def extract_version_from_condition(condition_str: str) -> tuple[str | None, str | None]:
    """Extract version and operator from a condition string.

    Returns: (version, operator) or (None, None) if no version found.

    Examples:
        "context.library < 'python@2.5.0'" -> ("2.5.0", "<")
        "context.library >= 'java@1.13.0'" -> ("1.13.0", ">=")
        "context.library < 'golang@2.1.0-dev'" -> ("2.1.0-dev", "<")
        "context.library == 'java'" -> (None, "==")

    """
    # Match the operator (longer operators first to avoid partial matches)
    op_match = re.search(r"context\.library(?:\.name|\.version)?\s*(==|!=|<=|>=|<|>)", condition_str)
    if not op_match:
        return None, None

    operator = op_match.group(1)

    # Extract the library@version string
    version_match = re.search(r"['\"]([a-z_]+@[^'\"]+)['\"]", condition_str)
    if version_match:
        lib_name, version = parse_library_version_from_string(version_match.group(1))
        if version:
            return version, operator

    # No version found, just operator
    return None, operator


def parse_version_range_condition(condition_str: str) -> tuple[str | None, str | None, str | None, str | None]:
    """Parse a version range condition like 'context.library >= "java@1.13.0" and context.library < "java@1.17.0"'.

    Returns: (library, min_version, min_op, max_version, max_op) or (None, None, None, None) if not a range.
    """
    # Match patterns like: context.library >= 'java@1.13.0' and context.library < 'java@1.17.0'
    pattern = (
        r"context\.library\s*(>=|>)\s*['\"]([a-z_]+)@([\d.]+)['\"]\s+and\s+"
        r"context\.library\s*(<|<=)\s*['\"][a-z_]+@([\d.]+)['\"]"
    )
    match = re.search(pattern, condition_str)
    if match:
        min_op, library, min_version, max_op, max_version = match.groups()
        return library, min_version, max_version, f"{min_op}{min_version} and {max_op}{max_version}"

    return None, None, None, None


def extract_reason_from_args(args_dict: dict[str, Any]) -> str | None:
    """Extract the reason from decorator arguments."""
    reason = args_dict.get("keyword", {}).get("reason")
    if reason:
        # Remove quotes from the reason string
        reason = reason.strip("'\"")
    return reason


def decorator_to_manifest_entry(decorator_info: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a parsed decorator to a manifest entry.

    This function is independent of the parsing stage - it takes a dictionary
    containing parsed decorator information and returns a manifest entry dict.

    Args:
        decorator_info: Dictionary with keys:
            - decorator: str (bug, flaky, missing_feature, irrelevant, incomplete_test_app)
            - args_dict: dict with 'positional' (list) and 'keyword' (dict)
            - nodeid: str (pytest nodeid like 'tests/file.py::Class::method')
            - is_simple: bool (whether decorator is simple enough for manifest)
            - rejection_reason: str (why decorator was rejected, if applicable)

    Returns:
        Dictionary with manifest entry information:
            - library: str (target library for the manifest file)
            - nodeid: str (test path for manifest)
            - entry: str (manifest entry value like 'v1.2.0' or 'missing_feature (reason)')
            - entry_type: str ('version' or 'marker')
            - original_decorator: str (the original decorator type)
            - notes: str (any additional notes about the conversion)

        Returns None if the decorator cannot be converted to a manifest entry.

    """
    if not decorator_info.get("is_simple", False):
        return None

    decorator_type = decorator_info["decorator"]
    args_dict = decorator_info.get("args_dict", {"positional": [], "keyword": {}})
    nodeid = decorator_info["nodeid"]

    # Extract library from keyword argument or condition
    library: str | None = None
    version: str | None = None
    operator: str | None = None
    reason = extract_reason_from_args(args_dict)

    # Check for library= keyword argument
    library_kwarg = args_dict.get("keyword", {}).get("library")
    if library_kwarg:
        library = library_kwarg.strip("'\"")

    # Check condition (positional arg or condition= keyword)
    condition_str: str | None = None
    if args_dict.get("positional"):
        condition_str = args_dict["positional"][0]
    elif args_dict.get("keyword", {}).get("condition"):
        condition_str = args_dict["keyword"]["condition"]

    if condition_str:
        # Try to extract library from condition
        if not library:
            library = extract_library_from_condition(condition_str)

        # Try to extract version from condition
        version, operator = extract_version_from_condition(condition_str)

        # Check for version range (e.g., >= 1.13.0 and < 1.17.0)
        if " and " in condition_str:
            range_lib, min_ver, max_ver, range_expr = parse_version_range_condition(condition_str)
            if range_lib:
                library = range_lib
                # For version ranges, we note it but can't express it directly in manifest
                # The manifest supports semver ranges, but the decorator condition might not map directly

    if not library:
        return None

    # Build the manifest entry
    entry: str
    entry_type: str
    notes: str = ""
    component_version: str | None = None  # For explicit format entries

    if version and operator:
        # Version-based condition
        if operator in ("<", "<="):
            # @missing_feature(context.library < "python@2.5.0") means feature available from v2.5.0
            # @bug(context.library < "java@1.0.0") means bug fixed in v1.0.0
            if decorator_type in ("missing_feature", "incomplete_test_app", "bug"):
                if reason:
                    # Use explicit format to preserve the description
                    entry = f"{decorator_type} ({reason})"
                    entry_type = "explicit"
                    component_version = f"{operator}{version}"
                    notes = f"Feature available from v{version}"
                else:
                    # No reason - use simple version format
                    entry = f"v{version}"
                    entry_type = "version"
                    notes = f"Feature available from v{version}"
            else:
                # irrelevant, flaky - keep as marker with reason
                entry = f"{decorator_type} ({reason})" if reason else decorator_type
                entry_type = "marker"
                notes = f"Applies to versions {operator} {version}"
        elif operator in (">", ">="):
            # @irrelevant(context.library >= "dotnet@3.7.0") means irrelevant from v3.7.0 onwards
            if reason:
                entry = f"{decorator_type} ({reason})"
                entry_type = "explicit"
                component_version = f"{operator}{version}"
            else:
                entry = f"{decorator_type}"
                entry_type = "marker"
            notes = f"Applies to versions {operator} {version}"
        elif operator == "==":
            # Equality with version is unusual, treat as marker
            entry = f"{decorator_type} ({reason})" if reason else decorator_type
            entry_type = "marker"
        elif operator == "!=":
            # Not equal - complex, treat as marker
            entry = f"{decorator_type} ({reason})" if reason else decorator_type
            entry_type = "marker"
            notes = f"Applies to all versions except {version}"
        else:
            entry = f"{decorator_type} ({reason})" if reason else decorator_type
            entry_type = "marker"
    elif operator == "==" and not version:
        # Simple equality without version: @bug(context.library == "java")
        entry = f"{decorator_type} ({reason})" if reason else decorator_type
        entry_type = "marker"
    elif operator == "!=" and not version:
        # Not equal without version: @irrelevant(context.library != 'golang')
        # This means "applies to all libraries except golang"
        # In manifest terms, this would go in OTHER library manifests, not golang
        notes = f"Applies to all libraries except {library}"
        entry = f"{decorator_type} ({reason})" if reason else decorator_type
        entry_type = "marker"
        # Flip the library logic - this entry should go in all OTHER manifests
        return {
            "library": f"NOT_{library}",  # Special marker to indicate this goes elsewhere
            "nodeid": nodeid,
            "entry": entry,
            "entry_type": entry_type,
            "original_decorator": decorator_type,
            "original_args": decorator_info.get("args", ""),
            "notes": notes,
            "inverted": True,
        }
    else:
        # No version, simple library match
        entry = f"{decorator_type} ({reason})" if reason else decorator_type
        entry_type = "marker"

    result = {
        "library": library,
        "nodeid": nodeid,
        "entry": entry,
        "entry_type": entry_type,
        "original_decorator": decorator_type,
        "original_args": decorator_info.get("args", ""),
        "notes": notes,
        "inverted": False,
    }

    # Add component_version for explicit format entries
    if component_version:
        result["component_version"] = component_version

    return result


def generate_manifest_entries(
    decorators: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Generate manifest entries from a list of parsed decorators.

    This function is independent of the parsing stage.

    Args:
        decorators: List of parsed decorator dictionaries

    Returns:
        Dictionary mapping library names to lists of manifest entries

    """
    manifest_entries: dict[str, list[dict[str, Any]]] = {}

    for dec_info in decorators:
        entry = decorator_to_manifest_entry(dec_info)
        if entry:
            library = entry["library"]
            if library not in manifest_entries:
                manifest_entries[library] = []
            manifest_entries[library].append(entry)

    return manifest_entries


def load_manifest_file(manifest_path: Path) -> dict[str, Any]:
    """Load and parse a manifest YAML file.

    Args:
        manifest_path: Path to the manifest YAML file

    Returns:
        Dictionary with the manifest contents, or empty dict if file doesn't exist

    """
    try:
        import yaml
    except ImportError:
        sys.stderr.write("Warning: PyYAML not installed. Cannot load manifest files.\n")
        sys.stderr.write("Install with: pip install pyyaml\n")
        return {}

    if not manifest_path.exists():
        return {}

    try:
        with manifest_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else {}
    except Exception as e:
        sys.stderr.write(f"Warning: Could not parse manifest {manifest_path}: {e}\n")
        return {}


def load_parsed_manifest_data(manifests_dir: Path | None = None) -> ManifestData | dict[str, Any]:
    """Load and parse all manifest files using the existing Manifest utility.

    Args:
        manifests_dir: Path to manifests directory

    Returns:
        ManifestData object with parsed manifest data, or empty dict if utils not available

    """
    if not MANIFEST_UTILS_AVAILABLE:
        sys.stderr.write("Warning: Manifest utilities not available. Using basic YAML loading.\n")
        return {}

    path = manifests_dir if manifests_dir else default_manifests_path
    try:
        return Manifest.parse(path)
    except Exception as e:
        sys.stderr.write(f"Warning: Could not parse manifests: {e}\n")
        return {}


def extract_nodeids_from_manifest(manifest_data: dict[str, Any]) -> set[str]:
    """Extract all nodeids (test paths) from a parsed manifest.

    Args:
        manifest_data: Parsed manifest dictionary

    Returns:
        Set of nodeid strings present in the manifest

    """
    nodeids: set[str] = set()

    manifest_section = manifest_data.get("manifest", {})
    if not manifest_section:
        return nodeids

    for nodeid in manifest_section.keys():
        nodeids.add(nodeid)

    return nodeids


def extract_manifest_entry_value(
    manifest_data: ManifestData | dict[str, Any],
    nodeid: str,
) -> tuple[SkipDeclaration | str | None, str | None]:
    """Extract the manifest entry value for a specific nodeid.

    Uses match_rule from the manifest library for proper nodeid matching.

    Args:
        manifest_data: Parsed ManifestData or raw YAML dictionary
        nodeid: Test path to look up

    Returns:
        Tuple of (declaration, component_version_str) or (None, None) if not found.
        Declaration can be SkipDeclaration object or string value.

    """
    # Use ManifestData with proper matching
    if MANIFEST_UTILS_AVAILABLE and isinstance(manifest_data, ManifestData):
        return _extract_from_manifest_data(manifest_data, nodeid)

    # Fall back to raw YAML parsing
    manifest_section = manifest_data.get("manifest", {})
    if not manifest_section:
        return None, None

    # First try exact match
    if nodeid in manifest_section:
        entry = manifest_section[nodeid]
        if MANIFEST_UTILS_AVAILABLE and isinstance(entry, str):
            try:
                decl = Declaration(entry, "unknown", is_inline=True)
                if decl.is_skip:
                    return SkipDeclaration(str(decl.value), decl.reason), None
            except (ValueError, AttributeError):
                pass
        return _normalize_manifest_entry_fallback(entry), None

    # Fall back to parent rule matching
    for rule in manifest_section.keys():
        if rule != nodeid and match_rule(rule, nodeid):
            entry = manifest_section[rule]
            if MANIFEST_UTILS_AVAILABLE and isinstance(entry, str):
                try:
                    decl = Declaration(entry, "unknown", is_inline=True)
                    if decl.is_skip:
                        return SkipDeclaration(str(decl.value), decl.reason), None
                except (ValueError, AttributeError):
                    pass
            return _normalize_manifest_entry_fallback(entry), None

    return None, None


def _extract_from_manifest_data(
    manifest_data: ManifestData,
    nodeid: str,
) -> tuple[SkipDeclaration | None, str | None]:
    """Extract manifest entry value from parsed ManifestData.

    Uses match_rule for proper nodeid matching and returns SkipDeclaration objects.
    Prioritizes exact matches over parent rule matches.

    Returns:
        Tuple of (declaration, component_version_str) or (None, None) if not found.

    """
    # First try exact match
    if nodeid in manifest_data:
        conditions = manifest_data[nodeid]
        if conditions:
            first_condition = conditions[0]
            declaration = first_condition.get("declaration")
            component_version = first_condition.get("component_version")
            cv_str = str(component_version) if component_version else None
            if declaration and isinstance(declaration, SkipDeclaration):
                return declaration, cv_str

    # Fall back to parent rule matching
    for rule in manifest_data.keys():
        if rule != nodeid and match_rule(rule, nodeid):
            conditions = manifest_data[rule]
            if conditions:
                first_condition = conditions[0]
                declaration = first_condition.get("declaration")
                component_version = first_condition.get("component_version")
                cv_str = str(component_version) if component_version else None
                if declaration and isinstance(declaration, SkipDeclaration):
                    return declaration, cv_str
            return None, None

    return None, None


def _normalize_manifest_entry_fallback(entry: Any) -> str:
    """Fallback normalization for raw manifest entries when utils not available."""
    if isinstance(entry, str):
        return entry.strip()

    if isinstance(entry, list):
        for item in entry:
            if isinstance(item, dict):
                if "weblog_declaration" in item:
                    weblog_decl = item["weblog_declaration"]
                    if "*" in weblog_decl:
                        return str(weblog_decl["*"]).strip()
                    if weblog_decl:
                        return str(next(iter(weblog_decl.values()))).strip()
                elif "declaration" in item:
                    return str(item["declaration"]).strip()

    return str(entry).strip()


def compare_manifest_entries(
    generated: str,
    existing: SkipDeclaration | str,
    generated_component_version: str | None = None,
) -> bool:
    """Compare a generated manifest entry with an existing one.

    Uses _parse_skip_declaration from the manifest library for parsing.

    Args:
        generated: Generated entry value string
        existing: Existing entry value (SkipDeclaration or string)
        generated_component_version: Optional component version for explicit format comparison

    Returns:
        True if entries are equivalent, False otherwise

    """
    gen_normalized = generated.strip()

    # If existing is already a SkipDeclaration, use it directly
    if MANIFEST_UTILS_AVAILABLE and isinstance(existing, SkipDeclaration):
        existing_declaration = existing.value
        existing_is_skip = True
    else:
        exist_normalized = str(existing).strip() if existing else ""
        # Exact string match
        if gen_normalized == exist_normalized:
            return True
        # Try to parse existing as skip declaration
        existing_declaration = None
        existing_is_skip = False
        if MANIFEST_UTILS_AVAILABLE:
            try:
                existing_declaration, _ = _parse_skip_declaration(exist_normalized)
                existing_is_skip = True
            except (ValueError, AssertionError):
                pass

    # Try to parse generated string using library function
    if MANIFEST_UTILS_AVAILABLE:
        try:
            gen_declaration, _ = _parse_skip_declaration(gen_normalized)
            gen_is_skip = True
        except (ValueError, AssertionError):
            gen_is_skip = False
            gen_declaration = None

        # Both are skip declarations - compare marker types
        if gen_is_skip and existing_is_skip and gen_declaration and existing_declaration:
            return gen_declaration == existing_declaration

        # One is skip, one is not - different
        if gen_is_skip != existing_is_skip:
            return False

    # Fall back to string comparison for non-skip entries (versions)
    if isinstance(existing, SkipDeclaration):
        return False  # Generated is version, existing is skip - different

    exist_normalized = str(existing).strip() if existing else ""

    # Exact match
    if gen_normalized == exist_normalized:
        return True

    return False


# Components list matching utils/manifest/_internal/parser.py
MANIFEST_COMPONENTS = (
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
)


def get_manifest_path_for_library(library: str, manifests_dir: Path | None = None) -> Path:
    """Get the manifest file path for a given library.

    Args:
        library: Library name (e.g., 'java', 'python')
        manifests_dir: Optional path to manifests directory

    Returns:
        Path to the manifest file

    """
    if manifests_dir is None:
        manifests_dir = default_manifests_path

    # Normalize library name to match manifest file naming
    lib_name = library.lower()

    # Verify it's a known component
    if lib_name not in MANIFEST_COMPONENTS:
        # Try some common variations
        lib_mapping = {
            "java_otel": "java",  # java_otel uses java manifest? Check this
            "nodejs_otel": "nodejs",
        }
        lib_name = lib_mapping.get(lib_name, lib_name)

    return manifests_dir / f"{lib_name}.yml"


def filter_entries_not_in_manifest(
    entries: list[dict[str, Any]],
    manifest_path: Path,
    parsed_manifest_data: ManifestData | dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Filter manifest entries to find those not already in the manifest.

    Uses match_rule from the manifest library for proper nodeid matching.

    Args:
        entries: List of generated manifest entry dictionaries
        manifest_path: Path to the existing manifest YAML file
        parsed_manifest_data: Optional pre-parsed ManifestData from Manifest.parse()

    Returns:
        Dictionary with three categories:
        - "new": entries NOT in the manifest (can be added)
        - "identical": entries in manifest with identical value
        - "different": entries in manifest but with different value

    """
    # Use parsed ManifestData if available, otherwise load raw YAML
    if parsed_manifest_data is not None and MANIFEST_UTILS_AVAILABLE:
        manifest_data: ManifestData | dict[str, Any] = parsed_manifest_data
        manifest_rules = set(parsed_manifest_data.keys())
    else:
        manifest_data = load_manifest_file(manifest_path)
        manifest_rules = extract_nodeids_from_manifest(manifest_data)

    new_entries: list[dict[str, Any]] = []
    identical_entries: list[dict[str, Any]] = []
    different_entries: list[dict[str, Any]] = []

    for entry in entries:
        nodeid = entry["nodeid"]
        generated_value = entry["entry"]
        generated_cv = entry.get("component_version")

        # Only check for EXACT nodeid match - parent rules don't count as conflicts
        # A method-level decorator can override a class-level manifest entry
        has_exact_match = nodeid in manifest_rules
        existing_value: SkipDeclaration | str | None = None
        existing_cv: str | None = None

        if has_exact_match:
            existing_value, existing_cv = extract_manifest_entry_value(manifest_data, nodeid)

        if not has_exact_match:
            # No exact match - this is a NEW entry (even if covered by a parent rule)
            new_entries.append(entry)
        elif existing_value is not None:
            # Exact match exists - compare the values
            entry_with_existing = entry.copy()
            # Convert SkipDeclaration to string for display
            existing_display = str(existing_value)
            if existing_cv:
                existing_display += f" [component_version: {existing_cv}]"
            entry_with_existing["existing_value"] = existing_display
            entry_with_existing["existing_component_version"] = existing_cv

            # Compare declaration and component_version
            decl_matches = compare_manifest_entries(generated_value, existing_value)
            cv_matches = (generated_cv == existing_cv) or (not generated_cv and not existing_cv)

            if decl_matches and cv_matches:
                identical_entries.append(entry_with_existing)
            else:
                different_entries.append(entry_with_existing)
        else:
            # Covered but couldn't extract value - treat as identical
            identical_entries.append(entry)

    return {
        "new": new_entries,
        "identical": identical_entries,
        "different": different_entries,
    }


def filter_manifest_data_by_component(
    manifest_data: ManifestData,
    component: str,
) -> ManifestData:
    """Filter ManifestData to only include conditions for a specific component.

    Args:
        manifest_data: Full ManifestData from Manifest.parse()
        component: Component name to filter by (e.g., 'java', 'python')

    Returns:
        New ManifestData with only conditions for the specified component

    """
    if not MANIFEST_UTILS_AVAILABLE:
        return manifest_data

    filtered = ManifestData()
    for nodeid, conditions in manifest_data.items():
        # Filter conditions for this component
        component_conditions = [c for c in conditions if c.get("component") == component]
        if component_conditions:
            filtered[nodeid] = component_conditions

    return filtered


def filter_all_entries_not_in_manifests(
    entries_by_library: dict[str, list[dict[str, Any]]],
    manifests_dir: Path | None = None,
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Filter all manifest entries across all libraries to find new entries.

    Uses the Manifest utility from utils/manifest if available for better parsing.

    Args:
        entries_by_library: Dictionary mapping library names to entry lists
        manifests_dir: Optional path to manifests directory

    Returns:
        Dictionary mapping library names to:
        {"new": [...], "identical": [...], "different": [...]}

    """
    results: dict[str, dict[str, list[dict[str, Any]]]] = {}

    # Load all manifest data once using the Manifest utility if available
    full_manifest_data: ManifestData | None = None
    if MANIFEST_UTILS_AVAILABLE:
        path = manifests_dir if manifests_dir else default_manifests_path
        try:
            full_manifest_data = Manifest.parse(path)
        except Exception as e:
            sys.stderr.write(f"Warning: Could not parse manifests with Manifest utility: {e}\n")
            full_manifest_data = None

    for library, entries in entries_by_library.items():
        # Skip inverted entries (NOT_*) for now
        if library.startswith("NOT_"):
            results[library] = {"new": entries, "identical": [], "different": []}
            continue

        manifest_path = get_manifest_path_for_library(library, manifests_dir)

        # Filter manifest data for this specific library/component
        library_manifest_data: ManifestData | dict[str, Any] | None = None
        if full_manifest_data is not None:
            library_manifest_data = filter_manifest_data_by_component(full_manifest_data, library)

        categorized = filter_entries_not_in_manifest(
            entries,
            manifest_path,
            parsed_manifest_data=library_manifest_data,
        )

        results[library] = categorized

    return results


def format_manifest_yaml(entries: list[dict[str, Any]], library: str) -> str:
    """Format manifest entries as YAML for a specific library.

    Args:
        entries: List of manifest entry dictionaries
        library: Library name for the manifest

    Returns:
        YAML formatted string

    """
    lines: list[str] = []
    lines.append(
        "# yaml-language-server: $schema=https://raw.githubusercontent.com/DataDog/system-tests/refs/heads/main/utils/manifest/schema.json"
    )
    lines.append("---")
    lines.append("manifest:")

    # Sort entries by nodeid for consistent output
    sorted_entries = sorted(entries, key=lambda e: e["nodeid"])

    for entry in sorted_entries:
        nodeid = entry["nodeid"]
        manifest_value = entry["entry"]
        notes = entry.get("notes", "")

        # Format the entry
        if notes:
            lines.append(f"  {nodeid}: {manifest_value}  # {notes}")
        else:
            lines.append(f"  {nodeid}: {manifest_value}")

    return "\n".join(lines) + "\n"


def output_manifest_entries(
    decorators: list[dict[str, Any]],
    output_format: str = "text",
    library_filter: str | None = None,
    filter_existing: bool = False,
    manifests_dir: Path | None = None,
    show_existing: bool = False,
    exclude_libraries: list[str] | None = None,
) -> None:
    """Output manifest entries generated from decorators.

    Args:
        decorators: List of parsed decorator dictionaries
        output_format: 'text', 'json', or 'yaml'
        library_filter: Optional library name to filter entries
        filter_existing: If True, filter out entries already in manifests
        manifests_dir: Path to manifests directory (for filtering)
        show_existing: If True, also show entries that are already in manifests
        exclude_libraries: Optional list of library names to exclude

    """
    manifest_data = generate_manifest_entries(decorators)

    if library_filter:
        manifest_data = {k: v for k, v in manifest_data.items() if k == library_filter}

    # Exclude libraries if specified
    if exclude_libraries:
        exclude_set = set(exclude_libraries)
        manifest_data = {k: v for k, v in manifest_data.items() if k not in exclude_set}

    # Filter out existing entries if requested
    filtered_results: dict[str, dict[str, list[dict[str, Any]]]] | None = None
    if filter_existing:
        filtered_results = filter_all_entries_not_in_manifests(manifest_data, manifests_dir)
        # Replace manifest_data with only new entries
        manifest_data = {lib: data["new"] for lib, data in filtered_results.items()}

    if output_format == "json":
        if filtered_results and show_existing:
            output: dict[str, Any] = {
                "new_entries": {lib: data["new"] for lib, data in filtered_results.items()},
                "identical_entries": {lib: data["identical"] for lib, data in filtered_results.items()},
                "different_entries": {lib: data["different"] for lib, data in filtered_results.items()},
                "summary": {
                    "total_new": sum(len(data["new"]) for data in filtered_results.values()),
                    "total_identical": sum(len(data["identical"]) for data in filtered_results.values()),
                    "total_different": sum(len(data["different"]) for data in filtered_results.values()),
                },
            }
            sys.stdout.write(json.dumps(output, indent=2) + "\n")
        else:
            sys.stdout.write(json.dumps(manifest_data, indent=2) + "\n")
    elif output_format == "yaml":
        for library, entries in sorted(manifest_data.items()):
            if not entries:
                continue
            if library.startswith("NOT_"):
                sys.stdout.write(f"\n# Entries for all libraries EXCEPT {library[4:]}:\n")
                sys.stdout.write("# These entries should be added to other library manifests\n")
            else:
                sys.stdout.write(f"\n# === {library}.yml ===\n")
            sys.stdout.write(format_manifest_yaml(entries, library))

        # Show different entries as comments in YAML mode
        if show_existing and filtered_results:
            has_different = any(data.get("different") for data in filtered_results.values())
            if has_different:
                sys.stdout.write("\n# " + "=" * 78 + "\n")
                sys.stdout.write("# ENTRIES WITH DIFFERENT VALUES (review needed)\n")
                sys.stdout.write("# " + "=" * 78 + "\n")
                for library, data in sorted(filtered_results.items()):
                    different = data.get("different", [])
                    if not different:
                        continue
                    sys.stdout.write(f"\n# --- {library} ({len(different)} different) ---\n")
                    for entry in sorted(different, key=lambda e: e["nodeid"]):
                        sys.stdout.write(f"#   {entry['nodeid']}\n")
                        sys.stdout.write(f"#     decorator: {entry['entry']}\n")
                        sys.stdout.write(f"#     manifest:  {entry.get('existing_value', '?')}\n")
    else:
        # Text format
        total_new = sum(len(entries) for entries in manifest_data.values())
        total_identical = 0
        total_different = 0
        if filtered_results:
            total_identical = sum(len(data["identical"]) for data in filtered_results.values())
            total_different = sum(len(data["different"]) for data in filtered_results.values())

        if filter_existing:
            sys.stdout.write(
                f"Found {total_new} NEW, {total_identical} IDENTICAL, {total_different} DIFFERENT entries\n"
            )
        else:
            sys.stdout.write(f"Generated {total_new} manifest entries for {len(manifest_data)} libraries\n")
        sys.stdout.write("=" * 100 + "\n\n")

        # Show NEW entries
        if total_new > 0:
            sys.stdout.write("NEW ENTRIES (not in manifest)\n")
            sys.stdout.write("-" * 100 + "\n\n")

            for library, entries in sorted(manifest_data.items()):
                if not entries:
                    continue

                if library.startswith("NOT_"):
                    sys.stdout.write(f"Library: ALL EXCEPT {library[4:]} ({len(entries)} new)\n")
                else:
                    sys.stdout.write(f"Library: {library} ({len(entries)} new)\n")
                sys.stdout.write("-" * 40 + "\n")

                for entry in sorted(entries, key=lambda e: e["nodeid"]):
                    sys.stdout.write(f"  {entry['nodeid']}\n")
                    sys.stdout.write(f"    -> {entry['entry']}\n")
                    if entry.get("component_version"):
                        sys.stdout.write(f"       component_version: {entry['component_version']}\n")
                    if entry.get("notes"):
                        sys.stdout.write(f"    # {entry['notes']}\n")
                    sys.stdout.write(f"    (from: @{entry['original_decorator']}({entry['original_args']}))\n")
                    sys.stdout.write("\n")

                sys.stdout.write("\n")

        # Show DIFFERENT entries (entries with different values)
        if show_existing and filtered_results and total_different > 0:
            sys.stdout.write("=" * 100 + "\n")
            sys.stdout.write("DIFFERENT ENTRIES (in manifest but with different value)\n")
            sys.stdout.write("=" * 100 + "\n\n")

            for library, data in sorted(filtered_results.items()):
                different = data.get("different", [])
                if not different:
                    continue

                sys.stdout.write(f"Library: {library} ({len(different)} different)\n")
                sys.stdout.write("-" * 40 + "\n")

                for entry in sorted(different, key=lambda e: e["nodeid"]):
                    sys.stdout.write(f"  {entry['nodeid']}\n")
                    sys.stdout.write(f"    decorator: {entry['entry']}\n")
                    sys.stdout.write(f"    manifest:  {entry.get('existing_value', '?')}\n")
                    sys.stdout.write(f"    (from: @{entry['original_decorator']}({entry['original_args']}))\n")
                    sys.stdout.write("\n")

                sys.stdout.write("\n")

        # Show IDENTICAL entries
        if show_existing and filtered_results and total_identical > 0:
            sys.stdout.write("=" * 100 + "\n")
            sys.stdout.write("IDENTICAL ENTRIES (in manifest with same value)\n")
            sys.stdout.write("=" * 100 + "\n\n")

            for library, data in sorted(filtered_results.items()):
                identical = data.get("identical", [])
                if not identical:
                    continue

                sys.stdout.write(f"Library: {library} ({len(identical)} identical)\n")
                sys.stdout.write("-" * 40 + "\n")

                for entry in sorted(identical, key=lambda e: e["nodeid"]):
                    sys.stdout.write(f"  {entry['nodeid']}\n")
                    sys.stdout.write(f"    -> {entry['entry']}\n")
                    sys.stdout.write("    (identical in manifest)\n")
                    sys.stdout.write("\n")

                sys.stdout.write("\n")


def output_text(
    results: list[dict[str, Any]],
    summary_only: bool = False,
    show_simplicity: bool = False,
    rejected: list[dict[str, Any]] | None = None,
) -> None:
    """Output results as formatted text."""
    # Group by decorator type for summary
    decorator_counts: dict[str, int] = {}
    for result in results:
        decorator_counts[result["decorator"]] = decorator_counts.get(result["decorator"], 0) + 1

    if not summary_only:
        # Print results
        for result in results:
            decorator = result["decorator"]
            args = result["args"]
            nodeid = result["nodeid"]
            line = result["line"]

            if args:
                sys.stdout.write(f"@{decorator}({args})\n")
            else:
                sys.stdout.write(f"@{decorator}\n")
            sys.stdout.write(f"  nodeid: {nodeid}\n")
            sys.stdout.write(f"  line: {line}\n")
            if show_simplicity:
                is_simple = result.get("is_simple", False)
                sys.stdout.write(f"  simple: {is_simple}\n")
                if not is_simple and result.get("rejection_reason"):
                    sys.stdout.write(f"  reason: {result['rejection_reason']}\n")
            sys.stdout.write("\n")

    # Print summary
    sys.stdout.write("=" * 100 + "\n")
    sys.stdout.write("SUMMARY\n")
    sys.stdout.write("=" * 100 + "\n")
    sys.stdout.write(f"Total decorators found: {len(results)}\n\n")
    for dec_name in sorted(decorator_counts.keys()):
        sys.stdout.write(f"  @{dec_name}: {decorator_counts[dec_name]}\n")

    # Print rejected decorators if requested
    if rejected:
        sys.stdout.write("\n" + "=" * 100 + "\n")
        sys.stdout.write("REJECTED DECORATORS\n")
        sys.stdout.write("=" * 100 + "\n")
        sys.stdout.write(f"Total rejected: {len(rejected)}\n\n")

        # Group by rejection reason
        by_reason: dict[str, list[dict[str, Any]]] = {}
        for r in rejected:
            reason = r.get("rejection_reason", "Unknown")
            if reason not in by_reason:
                by_reason[reason] = []
            by_reason[reason].append(r)

        for reason in sorted(by_reason.keys()):
            items = by_reason[reason]
            sys.stdout.write(f"\n--- {reason} ({len(items)}) ---\n")
            for item in items:
                decorator = item["decorator"]
                args = item["args"]
                nodeid = item["nodeid"]
                if args:
                    sys.stdout.write(f"  @{decorator}({args})\n")
                else:
                    sys.stdout.write(f"  @{decorator}\n")
                sys.stdout.write(f"    nodeid: {nodeid}\n")


def output_json(results: list[dict[str, Any]], rejected: list[dict[str, Any]] | None = None) -> None:
    """Output results as JSON."""
    output: dict[str, Any] = {
        "decorators": results,
        "summary": {
            "total": len(results),
            "by_type": {},
        },
    }

    for result in results:
        dec_type = result["decorator"]
        output["summary"]["by_type"][dec_type] = output["summary"]["by_type"].get(dec_type, 0) + 1

    if rejected:
        output["rejected"] = rejected
        output["summary"]["rejected_total"] = len(rejected)

        # Group by rejection reason
        by_reason: dict[str, int] = {}
        for r in rejected:
            reason = r.get("rejection_reason", "Unknown")
            by_reason[reason] = by_reason.get(reason, 0) + 1
        output["summary"]["rejected_by_reason"] = by_reason

    sys.stdout.write(json.dumps(output, indent=2) + "\n")


def get_decorator_line_range(filepath: Path, decorator_line: int) -> tuple[int, int]:
    """Get the full line range of a decorator (handles multiline decorators).

    Args:
        filepath: Path to the Python file
        decorator_line: Starting line number of the decorator (1-based)

    Returns:
        Tuple of (start_line, end_line) both 1-based, inclusive

    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return (decorator_line, decorator_line)

    # Find the decorator node at this line
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            for decorator in node.decorator_list:
                if decorator.lineno == decorator_line:
                    # end_lineno includes the full decorator expression
                    return (decorator.lineno, decorator.end_lineno or decorator.lineno)

    return (decorator_line, decorator_line)


def remove_decorator_from_file(
    filepath: Path,
    decorator_line: int,
    dry_run: bool = True,
) -> bool:
    """Remove a specific decorator from a Python file.

    Args:
        filepath: Path to the Python file
        decorator_line: Line number of the decorator to remove (1-based)
        dry_run: If True, don't actually modify the file

    Returns:
        True if successful, False otherwise

    """
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write(f"Error reading {filepath}: {e}\n")
        return False

    start_line, end_line = get_decorator_line_range(filepath, decorator_line)

    # Convert to 0-based indices
    start_idx = start_line - 1
    end_idx = end_line  # Keep end_idx as is since we want to exclude it in slice

    if start_idx < 0 or end_idx > len(lines):
        sys.stderr.write(f"Invalid line range {start_line}-{end_line} for {filepath}\n")
        return False

    # Remove the decorator lines
    new_lines = lines[:start_idx] + lines[end_idx:]

    if dry_run:
        return True

    try:
        filepath.write_text("".join(new_lines), encoding="utf-8")
        return True
    except OSError as e:
        sys.stderr.write(f"Error writing {filepath}: {e}\n")
        return False


def add_entry_to_manifest(
    manifest_path: Path,
    nodeid: str,
    entry_value: str,
    dry_run: bool = True,
    component_version: str | None = None,
) -> bool:
    """Add a new entry to a manifest file maintaining alphabetical order.

    Uses line-by-line insertion to preserve existing formatting.

    Args:
        manifest_path: Path to the manifest YAML file
        nodeid: The test nodeid (e.g., 'tests/path.py::Class::method')
        entry_value: The entry value (e.g., 'missing_feature (reason)')
        dry_run: If True, don't actually modify the file
        component_version: Optional version constraint for explicit format (e.g., '<4.19.0')

    Returns:
        True if successful, False otherwise

    """
    if not manifest_path.exists():
        sys.stderr.write(f"Manifest file not found: {manifest_path}\n")
        return False

    try:
        content = manifest_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
    except OSError as e:
        sys.stderr.write(f"Error reading {manifest_path}: {e}\n")
        return False

    # Check if nodeid already exists in the file (simple string search)
    if f"  {nodeid}:" in content:
        sys.stderr.write(f"Entry already exists for {nodeid} in {manifest_path}\n")
        return False

    if dry_run:
        return True

    # Find all top-level manifest entries (lines starting with exactly 2 spaces followed by tests/)
    entry_pattern = re.compile(r"^  (tests/[^:]+(?:::[^:]+)*):.*$")
    entries_with_positions: list[tuple[int, str]] = []

    for i, line in enumerate(lines):
        match = entry_pattern.match(line)
        if match:
            entries_with_positions.append((i, match.group(1)))

    # Find insertion point (alphabetical order)
    insert_idx = len(lines)  # Default to end
    for line_idx, existing_nodeid in entries_with_positions:
        if nodeid < existing_nodeid:
            insert_idx = line_idx
            break
        # If we're past this entry, insert after it (and any continuation lines)
        if line_idx == entries_with_positions[-1][0]:
            # Last entry - find where it ends
            insert_idx = line_idx + 1
            while insert_idx < len(lines):
                next_line = lines[insert_idx]
                # Stop if we hit another entry or end of manifest section
                if entry_pattern.match(next_line) or not next_line.startswith("  "):
                    break
                insert_idx += 1
        else:
            # Find next entry's position
            for next_line_idx, next_nodeid in entries_with_positions:
                if next_line_idx > line_idx:
                    if nodeid < next_nodeid:
                        insert_idx = next_line_idx
                    break

    # Format the new entry line(s)
    if component_version:
        # Explicit format with declaration and component_version
        # Quote the declaration value if needed
        needs_quoting = any(c in entry_value for c in ":{}[]&*#?|<>=!%@\\")
        if needs_quoting and not (entry_value.startswith('"') or entry_value.startswith("'")):
            escaped_value = entry_value.replace("'", "''")
            formatted_declaration = f"'{escaped_value}'"
        else:
            formatted_declaration = entry_value

        # Quote component_version if it starts with special YAML characters (>, <, etc.)
        if component_version.startswith(("<", ">", "|", "*", "&", "!", "%", "@", "`")):
            formatted_cv = f"'{component_version}'"
        else:
            formatted_cv = component_version

        # Multi-line format:
        #   nodeid:
        #     - declaration: value
        #       component_version: '<version'
        new_lines_to_insert = [
            f"  {nodeid}:\n",
            f"    - declaration: {formatted_declaration}\n",
            f"      component_version: {formatted_cv}\n",
        ]
        for i, line in enumerate(new_lines_to_insert):
            lines.insert(insert_idx + i, line)
    else:
        # Simple inline format
        # Quote value if it contains special YAML characters
        needs_quoting = any(c in entry_value for c in ":{}[]&*#?|<>=!%@\\")
        if needs_quoting and not (entry_value.startswith('"') or entry_value.startswith("'")):
            escaped_value = entry_value.replace("'", "''")
            formatted_value = f"'{escaped_value}'"
        else:
            formatted_value = entry_value

        new_line = f"  {nodeid}: {formatted_value}\n"
        lines.insert(insert_idx, new_line)

    try:
        manifest_path.write_text("".join(lines), encoding="utf-8")
        return True
    except OSError as e:
        sys.stderr.write(f"Error writing {manifest_path}: {e}\n")
        return False


def migrate_decorators(
    entries_to_migrate: list[dict[str, Any]],
    manifests_dir: Path,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Migrate decorators to manifest files.

    For each entry:
    1. Add the entry to the appropriate manifest file
    2. Remove the decorator from the Python source file

    Args:
        entries_to_migrate: List of entries from filter_entries_not_in_manifest 'new' category
        manifests_dir: Path to manifests directory
        dry_run: If True, don't actually modify files

    Returns:
        Dictionary with migration results:
        - 'success': list of successfully migrated entries
        - 'failed_manifest': list of entries that failed to add to manifest
        - 'failed_remove': list of entries where decorator removal failed

    """
    results: dict[str, list[dict[str, Any]]] = {
        "success": [],
        "failed_manifest": [],
        "failed_remove": [],
    }

    # Group entries by file to handle multiple decorators in same file
    # We need to process removals from bottom to top to preserve line numbers
    entries_by_file: dict[str, list[dict[str, Any]]] = {}
    for entry in entries_to_migrate:
        filepath = entry.get("file", "")
        if filepath not in entries_by_file:
            entries_by_file[filepath] = []
        entries_by_file[filepath].append(entry)

    # Sort entries within each file by line number (descending) for removal
    for filepath in entries_by_file:
        entries_by_file[filepath].sort(key=lambda e: e.get("line", 0), reverse=True)

    # Track which manifest entries have been successfully added
    manifest_added: set[tuple[str, str]] = set()

    for filepath, file_entries in entries_by_file.items():
        for entry in file_entries:
            library = entry.get("library", "")
            nodeid = entry.get("nodeid", "")
            entry_value = entry.get("entry", "")
            component_version = entry.get("component_version")
            line = entry.get("line", 0)

            # Skip inverted entries (NOT_library) for now
            if library.startswith("NOT_"):
                sys.stderr.write(f"Skipping inverted entry for {nodeid}\n")
                continue

            manifest_path = manifests_dir / f"{library}.yml"

            # Try to add to manifest
            manifest_key = (nodeid, library)
            if manifest_key not in manifest_added:
                if add_entry_to_manifest(
                    manifest_path,
                    nodeid,
                    entry_value,
                    dry_run=dry_run,
                    component_version=component_version,
                ):
                    manifest_added.add(manifest_key)
                else:
                    entry["error"] = "Failed to add to manifest"
                    results["failed_manifest"].append(entry)
                    continue

            # Try to remove decorator from source file
            source_path = Path(filepath)
            if not source_path.is_absolute():
                source_path = Path(__file__).parent / filepath

            if remove_decorator_from_file(source_path, line, dry_run=dry_run):
                results["success"].append(entry)
            else:
                entry["error"] = "Failed to remove decorator"
                results["failed_remove"].append(entry)

    return results


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="List decorators (bug, flaky, incomplete_test_app, irrelevant, missing_feature) in tests"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--summary", action="store_true", help="Show only summary counts")
    parser.add_argument(
        "--decorator",
        "-d",
        choices=list(TARGET_DECORATORS),
        action="append",
        help="Filter by decorator type (can be specified multiple times)",
    )
    parser.add_argument("--tests-dir", type=Path, help="Path to tests directory (default: ./tests)")
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory names to exclude from scanning (can be specified multiple times)",
    )
    parser.add_argument(
        "--exclude-pattern",
        action="append",
        default=[],
        help="Glob patterns to exclude files (e.g., '**/test_otel*.py', can be specified multiple times)",
    )
    parser.add_argument(
        "--exclude-library",
        action="append",
        default=[],
        help="Exclude decorators targeting specific libraries (e.g., 'python', can be specified multiple times)",
    )

    # Simplicity filtering options
    simplicity_group = parser.add_mutually_exclusive_group()
    simplicity_group.add_argument(
        "--simple",
        action="store_true",
        help="Show only simple decorators (single library condition, no force_skip=True)",
    )
    simplicity_group.add_argument(
        "--complex",
        action="store_true",
        help="Show only complex decorators (not simple)",
    )
    parser.add_argument(
        "--show-rejected",
        action="store_true",
        help="When filtering with --simple, also show rejected (complex) decorators",
    )
    parser.add_argument(
        "--show-simplicity",
        action="store_true",
        help="Show simplicity status for each decorator",
    )

    # Manifest generation options
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Generate manifest entries from simple decorators",
    )
    parser.add_argument(
        "--manifest-format",
        choices=["text", "json", "yaml"],
        default="text",
        help="Output format for manifest entries (default: text)",
    )
    parser.add_argument(
        "--manifest-library",
        type=str,
        help="Filter manifest entries for a specific library",
    )
    parser.add_argument(
        "--filter-existing",
        action="store_true",
        help="Filter out entries that are already in the manifest files",
    )
    parser.add_argument(
        "--manifests-dir",
        type=Path,
        help="Path to manifests directory (default: ./manifests)",
    )
    parser.add_argument(
        "--show-existing",
        action="store_true",
        help="When filtering, also show entries that are already in manifests",
    )

    # Migration options
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Migrate simple decorators: add NEW entries to manifests and remove decorators from source files",
    )
    parser.add_argument(
        "--remove-redundant",
        action="store_true",
        help="Remove decorators that have identical entries already in manifests (no manifest changes)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --migrate or --remove-redundant, show what would be done without making changes",
    )

    args = parser.parse_args()

    # Find tests directory
    if args.tests_dir:
        tests_dir = args.tests_dir.resolve()
    else:
        script_dir = Path(__file__).parent.resolve()
        tests_dir = script_dir / "tests"

    if not tests_dir.exists():
        sys.stderr.write(f"Error: Tests directory not found at {tests_dir}\n")
        sys.exit(1)

    exclude_dirs = args.exclude_dir if args.exclude_dir else None
    exclude_patterns = args.exclude_pattern if args.exclude_pattern else None
    if not args.json and not args.manifest:
        exclusions = []
        if exclude_dirs:
            exclusions.append(f"dirs: {', '.join(exclude_dirs)}")
        if exclude_patterns:
            exclusions.append(f"patterns: {', '.join(exclude_patterns)}")
        exclude_msg = f" (excluding {'; '.join(exclusions)})" if exclusions else ""
        sys.stderr.write(f"Scanning {tests_dir} for decorators{exclude_msg}...\n")

    all_results: list[dict[str, Any]] = []

    for filepath in find_python_files(tests_dir, exclude_dirs=exclude_dirs, exclude_patterns=exclude_patterns):
        results = extract_decorators_from_file(filepath, tests_dir)
        all_results.extend(results)

    # Filter by decorator type if specified
    if args.decorator:
        filter_set = set(args.decorator)
        all_results = [r for r in all_results if r["decorator"] in filter_set]

    # Determine manifests directory
    manifests_dir = args.manifests_dir
    if manifests_dir is None:
        manifests_dir = Path(__file__).parent / "manifests"

    # Handle migration mode
    if args.migrate:
        # For migration, we only use simple decorators with NEW entries
        simple_decorators = [r for r in all_results if r.get("is_simple", False)]

        # Generate manifest entries
        manifest_data = generate_manifest_entries(simple_decorators)

        # Filter by library if specified
        if args.manifest_library:
            manifest_data = {k: v for k, v in manifest_data.items() if k == args.manifest_library}

        # Exclude libraries if specified
        if args.exclude_library:
            exclude_set = set(args.exclude_library)
            manifest_data = {k: v for k, v in manifest_data.items() if k not in exclude_set}

        # Filter to only NEW entries
        filtered_results = filter_all_entries_not_in_manifests(manifest_data, manifests_dir)

        # Collect all NEW entries with their source file info
        entries_to_migrate: list[dict[str, Any]] = []
        for library, categories in filtered_results.items():
            for entry in categories.get("new", []):
                # Find the original decorator info to get file and line
                for dec in simple_decorators:
                    if dec["nodeid"] == entry["nodeid"]:
                        entry["file"] = dec["file"]
                        entry["line"] = dec["line"]
                        entry["library"] = library
                        entries_to_migrate.append(entry)
                        break

        if not entries_to_migrate:
            sys.stdout.write("No NEW entries to migrate.\n")
            return

        # Show what will be migrated
        dry_run = args.dry_run
        mode = "DRY RUN - " if dry_run else ""
        sys.stdout.write(f"\n{mode}Migrating {len(entries_to_migrate)} decorator(s)...\n")
        sys.stdout.write("=" * 80 + "\n")

        for entry in entries_to_migrate:
            sys.stdout.write(f"\n  {entry['nodeid']}\n")
            sys.stdout.write(f"    Library: {entry['library']}\n")
            sys.stdout.write(f"    Entry: {entry['entry']}\n")
            if entry.get("component_version"):
                sys.stdout.write(f"    Version: {entry['component_version']}\n")
            sys.stdout.write(f"    File: {entry['file']}:{entry['line']}\n")

        sys.stdout.write("\n" + "=" * 80 + "\n")

        if dry_run:
            sys.stdout.write("\nDry run complete. Use --migrate without --dry-run to apply changes.\n")
            return

        # Perform migration
        results = migrate_decorators(entries_to_migrate, manifests_dir, dry_run=False)

        # Report results
        sys.stdout.write("\nMigration complete:\n")
        sys.stdout.write(f"  Success: {len(results['success'])}\n")
        sys.stdout.write(f"  Failed (manifest): {len(results['failed_manifest'])}\n")
        sys.stdout.write(f"  Failed (remove): {len(results['failed_remove'])}\n")

        if results["failed_manifest"]:
            sys.stdout.write("\nFailed to add to manifest:\n")
            for entry in results["failed_manifest"]:
                sys.stdout.write(f"  - {entry['nodeid']}: {entry.get('error', 'Unknown error')}\n")

        if results["failed_remove"]:
            sys.stdout.write("\nFailed to remove decorator:\n")
            for entry in results["failed_remove"]:
                sys.stdout.write(f"  - {entry['nodeid']}: {entry.get('error', 'Unknown error')}\n")

        return

    # Handle remove-redundant mode
    if args.remove_redundant:
        # For removing redundant, we only use simple decorators with IDENTICAL entries
        simple_decorators = [r for r in all_results if r.get("is_simple", False)]

        # Generate manifest entries
        manifest_data = generate_manifest_entries(simple_decorators)

        # Filter by library if specified
        if args.manifest_library:
            manifest_data = {k: v for k, v in manifest_data.items() if k == args.manifest_library}

        # Exclude libraries if specified
        if args.exclude_library:
            exclude_set = set(args.exclude_library)
            manifest_data = {k: v for k, v in manifest_data.items() if k not in exclude_set}

        # Filter to find IDENTICAL entries
        filtered_results = filter_all_entries_not_in_manifests(manifest_data, manifests_dir)

        # Collect all IDENTICAL entries with their source file info
        entries_to_remove: list[dict[str, Any]] = []
        for library, categories in filtered_results.items():
            for entry in categories.get("identical", []):
                # Find the original decorator info to get file and line
                for dec in simple_decorators:
                    if dec["nodeid"] == entry["nodeid"]:
                        entry["file"] = dec["file"]
                        entry["line"] = dec["line"]
                        entry["library"] = library
                        entries_to_remove.append(entry)
                        break

        if not entries_to_remove:
            sys.stdout.write("No redundant decorators to remove.\n")
            return

        # Group by file and sort by line (descending) for safe removal
        entries_by_file: dict[str, list[dict[str, Any]]] = {}
        for entry in entries_to_remove:
            filepath = entry.get("file", "")
            if filepath not in entries_by_file:
                entries_by_file[filepath] = []
            entries_by_file[filepath].append(entry)

        for filepath in entries_by_file:
            entries_by_file[filepath].sort(key=lambda e: e.get("line", 0), reverse=True)

        # Show what will be removed
        dry_run = args.dry_run
        mode = "DRY RUN - " if dry_run else ""
        sys.stdout.write(f"\n{mode}Removing {len(entries_to_remove)} redundant decorator(s)...\n")
        sys.stdout.write("=" * 80 + "\n")

        for entry in entries_to_remove:
            sys.stdout.write(f"\n  {entry['nodeid']}\n")
            sys.stdout.write(f"    Library: {entry['library']}\n")
            entry_display = entry["entry"]
            if entry.get("component_version"):
                entry_display += f" [component_version: {entry['component_version']}]"
            sys.stdout.write(f"    Entry: {entry_display}\n")
            sys.stdout.write(f"    Existing: {entry.get('existing_value', 'N/A')}\n")
            sys.stdout.write(f"    File: {entry['file']}:{entry['line']}\n")

        sys.stdout.write("\n" + "=" * 80 + "\n")

        if dry_run:
            sys.stdout.write("\nDry run complete. Use --remove-redundant without --dry-run to apply.\n")
            return

        # Perform removal (process files in order, entries within each file from bottom to top)
        success_count = 0
        failed: list[dict[str, Any]] = []

        for filepath, file_entries in entries_by_file.items():
            source_path = Path(filepath)
            if not source_path.is_absolute():
                source_path = Path(__file__).parent / filepath

            for entry in file_entries:
                line = entry.get("line", 0)
                if remove_decorator_from_file(source_path, line, dry_run=False):
                    success_count += 1
                else:
                    entry["error"] = "Failed to remove decorator"
                    failed.append(entry)

        # Report results
        sys.stdout.write("\nRemoval complete:\n")
        sys.stdout.write(f"  Success: {success_count}\n")
        sys.stdout.write(f"  Failed: {len(failed)}\n")

        if failed:
            sys.stdout.write("\nFailed to remove:\n")
            for entry in failed:
                sys.stdout.write(f"  - {entry['nodeid']}: {entry.get('error', 'Unknown error')}\n")

        return

    # Handle manifest generation mode
    if args.manifest:
        # For manifest generation, we only use simple decorators
        simple_decorators = [r for r in all_results if r.get("is_simple", False)]

        output_manifest_entries(
            simple_decorators,
            output_format=args.manifest_format,
            library_filter=args.manifest_library,
            filter_existing=args.filter_existing,
            manifests_dir=manifests_dir,
            show_existing=args.show_existing,
            exclude_libraries=args.exclude_library if args.exclude_library else None,
        )
        return

    # Filter by simplicity
    rejected: list[dict[str, Any]] | None = None
    if args.simple:
        rejected = [r for r in all_results if not r.get("is_simple", False)]
        all_results = [r for r in all_results if r.get("is_simple", False)]
        if not args.show_rejected:
            rejected = None
    elif args.complex:
        # Show complex decorators, rejected are the simple ones
        rejected = [r for r in all_results if r.get("is_simple", False)]
        all_results = [r for r in all_results if not r.get("is_simple", False)]
        if not args.show_rejected:
            rejected = None

    # Output
    if args.json:
        output_json(all_results, rejected=rejected)
    else:
        output_text(
            all_results,
            summary_only=args.summary,
            show_simplicity=args.show_simplicity or args.simple or args.complex,
            rejected=rejected,
        )


if __name__ == "__main__":
    main()
