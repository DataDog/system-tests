import ast
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


DecoratorInfo = dict[str, Any]


def _decorator_name_matches(node: ast.AST, target_name: str) -> bool:
    """Check whether a decorator node refers to the given decorator name.

    Handles:
      @foo
      @pkg.foo
      @pkg.sub.foo

    We consider a match if the *final* name segment equals target_name.
    """
    # @foo
    if isinstance(node, ast.Name):
        return node.id == target_name

    # @pkg.foo or @pkg.sub.foo
    if isinstance(node, ast.Attribute):
        return _decorator_name_matches(
            node.attr if isinstance(node.attr, ast.AST) else ast.Name(id=node.attr), target_name
        ) or (node.attr == target_name)

    return False


def _get_decorator_base_name(node: ast.AST) -> str | None:
    """Extract the base name of a decorator (the last attribute / id), if any."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _decorator_call_matches(decorator: ast.expr, target_name: str) -> bool:
    """Check if a decorator (which might be a Call or a bare name/attribute)
    matches the target decorator name.
    """
    # @decorator(...)
    if isinstance(decorator, ast.Call):
        return _decorator_name_matches(decorator.func, target_name)

    # @decorator (no call)
    return _decorator_name_matches(decorator, target_name)


def _expr_to_source(expr: ast.AST, source: str) -> str:
    """Try to retrieve the exact source code for an expression.
    Fallback to a simple repr-style string if needed.
    """
    try:
        segment = ast.get_source_segment(source, expr)
        if segment is not None:
            return segment
    except Exception:
        pass

    # Fallback: very rough representation
    if isinstance(expr, ast.Constant):
        return repr(expr.value)
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return f"{_expr_to_source(expr.value, source)}.{expr.attr}"
    return ast.dump(expr)


def _collect_decorator_info(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    decorator: ast.expr,
    filename: str,
    source: str,
    class_name: str | None = None,
    decorator_index: int | None = None,
) -> DecoratorInfo:
    """Build a dictionary with information about one decorator usage on a function or class."""
    # Determine what is decorated
    if isinstance(node, ast.ClassDef):
        decorated_type = "class"
    elif isinstance(node, ast.AsyncFunctionDef):
        decorated_type = "async_function"
    else:
        decorated_type = "function"

    # If the decorator is a call, extract args and keywords
    if isinstance(decorator, ast.Call):
        call_node = decorator
        base_name = _get_decorator_base_name(call_node.func)
        args = [_expr_to_source(a, source) for a in call_node.args]
        keywords = {
            (kw.arg if kw.arg is not None else "**"): _expr_to_source(kw.value, source) for kw in call_node.keywords
        }
    else:
        call_node = None
        base_name = _get_decorator_base_name(decorator)
        args = []
        keywords = {}

    return {
        "file": filename,
        "lineno": node.lineno,
        "col_offset": node.col_offset,
        "decorated_type": decorated_type,  # "function" | "async_function" | "class"
        "decorated_name": getattr(node, "name", None),
        "class_name": class_name,  # Name of the class containing the decorated function, or None
        "decorator_base_name": base_name,
        "decorator_is_call": isinstance(decorator, ast.Call),
        "decorator_source": _expr_to_source(decorator, source),
        "args": args,
        "keywords": keywords,
        "decorator_index": decorator_index,  # Index in decorator_list for deletion
        "decorator_node": decorator,  # Store AST node for deletion
        "node_ast": node,  # Store the node AST for deletion
    }


def find_decorator_usages(
    root_dir: str | Path,
    decorator_name: str,
    *,
    include_undecorated_calls: bool = False,
) -> list[DecoratorInfo]:
    """Recursively scan all .py files under `root_dir` and collect information
    about uses of a decorator with the given name.

    This returns a list of dictionaries with keys such as:
      - file
      - lineno
      - col_offset
      - decorated_type  ("function", "async_function", "class")
      - decorated_name
      - class_name  (name of the class containing the decorated function, or None)
      - decorator_base_name
      - decorator_is_call (bool)
      - decorator_source (string representation)
      - args  (list of arg source strings)
      - keywords (dict name -> value source string)

    Matching logic:
      - Matches @decorator, @decorator(...), @pkg.decorator, @pkg.decorator(...)
        when the last part (e.g., 'decorator') equals `decorator_name`.

    If include_undecorated_calls=True, also includes *free-standing* calls
    to that decorator (e.g., decorator(...)) that are not used as decorators,
    with decorated_type="call" and decorated_name=None.
    """
    root_dir = Path(root_dir)
    results: list[DecoratorInfo] = []

    for path in root_dir.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            # Skip files with invalid syntax
            continue

        # Find decorators on functions/classes
        # We need to track class context, so we can't use ast.walk() directly
        # Instead, we'll traverse the tree manually to track parent classes
        def visit_node(node: ast.AST, current_class: str | None = None) -> None:
            """Recursively visit AST nodes, tracking the current class context."""
            if isinstance(node, ast.ClassDef):
                # Enter a new class context
                for idx, dec in enumerate(node.decorator_list):
                    if _decorator_call_matches(dec, decorator_name):
                        info = _collect_decorator_info(
                            node=node,
                            decorator=dec,
                            filename=str(path),
                            source=source,
                            class_name=None,  # Classes themselves don't have a parent class
                            decorator_index=idx,
                        )
                        results.append(info)
                # Visit children with this class as the current context
                for child in ast.iter_child_nodes(node):
                    visit_node(child, node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check decorators on functions
                for idx, dec in enumerate(node.decorator_list):
                    if _decorator_call_matches(dec, decorator_name):
                        info = _collect_decorator_info(
                            node=node,
                            decorator=dec,
                            filename=str(path),
                            source=source,
                            class_name=current_class,
                            decorator_index=idx,
                        )
                        results.append(info)
                # Visit children (nested functions) with the same class context
                for child in ast.iter_child_nodes(node):
                    visit_node(child, current_class)
            else:
                # Visit children with the same class context
                for child in ast.iter_child_nodes(node):
                    visit_node(child, current_class)

        visit_node(tree)

        # Optionally: find free-standing calls to the same decorator
        if include_undecorated_calls:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _decorator_name_matches(node.func, decorator_name):
                    results.append(
                        {
                            "file": str(path),
                            "lineno": node.lineno,
                            "col_offset": node.col_offset,
                            "decorated_type": "call",
                            "decorated_name": None,
                            "class_name": None,  # Free-standing calls don't belong to a class
                            "decorator_base_name": _get_decorator_base_name(node.func),
                            "decorator_is_call": True,
                            "decorator_source": _expr_to_source(node, source),
                            "args": [_expr_to_source(a, source) for a in node.args],
                            "keywords": {
                                (kw.arg if kw.arg is not None else "**"): _expr_to_source(kw.value, source)
                                for kw in node.keywords
                            },
                        }
                    )

    return results


def _build_nodeid(file_path: str, class_name: str | None, function_name: str | None) -> str:
    """Build a pytest nodeid from file path, class name, and function name.

    Format: tests/path/to/file.py::ClassName::method_name
    or: tests/path/to/file.py::ClassName (for class-level)
    or: tests/path/to/file.py::function_name (for module-level)
    """
    # Convert absolute path to relative path from workspace root
    path = Path(file_path)
    if path.is_absolute():
        # Try to make it relative - assume tests/ is the base
        try:
            # Find tests/ in the path
            parts = path.parts
            if "tests" in parts:
                idx = parts.index("tests")
                path = Path(*parts[idx:])
            else:
                # Fallback: use filename only
                path = Path(path.name)
        except Exception:
            path = Path(path.name)

    # Ensure it starts with tests/
    if not str(path).startswith("tests/"):
        path = Path("tests") / path

    nodeid_parts = [str(path)]

    if class_name:
        nodeid_parts.append(class_name)

    if function_name:
        nodeid_parts.append(function_name)

    return "::".join(nodeid_parts)


def _parse_weblog_variant_condition(condition_str: str) -> dict[str, Any] | None:
    """Parse conditions involving context.weblog_variant.

    Handles patterns like:
    - context.weblog_variant == "spring-boot"
    - context.weblog_variant != "rails70"
    - context.weblog_variant not in ["express4", "express5"]
    - "spring-boot" not in context.weblog_variant

    Returns a dict with:
    - weblog_names: list of weblog names (positive matches)
    - excluded_weblog_names: list of weblog names (negative matches)
    - operator: "==", "!=", "in", "not_in"
    """
    result = {
        "weblog_names": [],
        "excluded_weblog_names": [],
    }

    # Pattern 1: context.weblog_variant == "weblog-name"
    pattern1 = r'context\.weblog_variant\s*==\s*"([^"]+)"'
    match1 = re.search(pattern1, condition_str)
    if match1:
        result["weblog_names"].append(match1.group(1))
        result["operator"] = "=="
        return result

    # Pattern 2: context.weblog_variant != "weblog-name"
    pattern2 = r'context\.weblog_variant\s*!=\s*"([^"]+)"'
    match2 = re.search(pattern2, condition_str)
    if match2:
        result["excluded_weblog_names"].append(match2.group(1))
        result["operator"] = "!="
        return result

    # Pattern 3: context.weblog_variant not in ["weblog1", "weblog2"]
    pattern3 = r"context\.weblog_variant\s+not\s+in\s+\[([^\]]+)\]"
    match3 = re.search(pattern3, condition_str)
    if match3:
        # Extract weblog names from the list
        weblog_list_str = match3.group(1)
        # Parse quoted strings
        weblog_names = re.findall(r'"([^"]+)"', weblog_list_str)
        result["excluded_weblog_names"].extend(weblog_names)
        result["operator"] = "not_in"
        return result

    # Pattern 4: context.weblog_variant in ["weblog1", "weblog2"] or in ("weblog1", "weblog2")
    pattern4a = r"context\.weblog_variant\s+in\s+\[([^\]]+)\]"
    match4a = re.search(pattern4a, condition_str)
    if match4a:
        weblog_list_str = match4a.group(1)
        weblog_names = re.findall(r'"([^"]+)"', weblog_list_str)
        result["weblog_names"].extend(weblog_names)
        result["operator"] = "in"
        return result

    # Pattern 4b: context.weblog_variant in ("weblog1", "weblog2")
    pattern4b = r"context\.weblog_variant\s+in\s+\(([^)]+)\)"
    match4b = re.search(pattern4b, condition_str)
    if match4b:
        weblog_list_str = match4b.group(1)
        weblog_names = re.findall(r'"([^"]+)"', weblog_list_str)
        result["weblog_names"].extend(weblog_names)
        result["operator"] = "in"
        return result

    # Pattern 5: "weblog-name" not in context.weblog_variant
    pattern5 = r'"([^"]+)"\s+not\s+in\s+context\.weblog_variant'
    match5 = re.search(pattern5, condition_str)
    if match5:
        result["excluded_weblog_names"].append(match5.group(1))
        result["operator"] = "not_in_string"
        return result

    # Pattern 6: "weblog-name" in context.weblog_variant
    pattern6 = r'"([^"]+)"\s+in\s+context\.weblog_variant'
    match6 = re.search(pattern6, condition_str)
    if match6:
        result["weblog_names"].append(match6.group(1))
        result["operator"] = "in_string"
        return result

    return None


def _is_complex_condition(condition_str: str) -> bool:
    """Check if a condition string contains complex operators (AND, OR) that we don't support.

    Args:
        condition_str: The condition string to check

    Returns:
        True if the condition contains AND/OR operators, False otherwise

    """
    # Check for 'and' or 'or' operators (case-insensitive)
    # Use word boundaries to avoid matching words like "android" or "orchestrion"
    pattern = r"\b(and|or)\b"
    return bool(re.search(pattern, condition_str, re.IGNORECASE))


def _parse_component_condition(condition_str: str) -> dict[str, Any] | None:
    """Parse a condition string like 'context.library < "dotnet@2.21.0"' or
    'context.agent_version >= "7.36.0"'.

    Also handles:
    - context.library in ["java", "python"]
    - context.library in ("java", "python")

    Returns a dict with:
    - component: component name (e.g., "dotnet", "agent") or list of components for "in" operator
    - operator: comparison operator (e.g., "<", ">=", "in")
    - version: version string (e.g., "2.21.0", "7.36.0")
    - component_type: "library" or "agent_version"
    - is_equality: True if operator is == or != (these are handled differently)
    - component_list: list of component names when operator is "in"
    """
    # First check for "in" operator with library
    # Pattern: context.library in ["java", "python"] or context.library in ("java", "python")
    pattern_in_list = r"context\.library\s+in\s+\[([^\]]+)\]"
    match_in_list = re.search(pattern_in_list, condition_str)
    if match_in_list:
        component_list_str = match_in_list.group(1)
        component_names = re.findall(r'"([^"]+)"', component_list_str)
        return {
            "component": None,  # Will use component_list instead
            "component_type": "library",
            "operator": "in",
            "version": None,
            "version_str": None,
            "is_equality": False,
            "component_list": component_names,
        }

    # Pattern: context.library in ("java", "python")
    pattern_in_tuple = r"context\.library\s+in\s+\(([^)]+)\)"
    match_in_tuple = re.search(pattern_in_tuple, condition_str)
    if match_in_tuple:
        component_list_str = match_in_tuple.group(1)
        component_names = re.findall(r'"([^"]+)"', component_list_str)
        return {
            "component": None,  # Will use component_list instead
            "component_type": "library",
            "operator": "in",
            "version": None,
            "version_str": None,
            "is_equality": False,
            "component_list": component_names,
        }

    # Pattern to match: context.library < "dotnet@2.21.0" or context.agent_version >= "7.36.0"
    pattern = r'context\.(library|agent_version|weblog)\s*(<|<=|>|>=|==|!=)\s*"([^"]+)"'
    match = re.search(pattern, condition_str)

    if not match:
        return None

    component_type, operator, version_str = match.groups()

    is_equality = operator in ("==", "!=")

    # Extract component name from version string if it's library
    if component_type == "library":
        if "@" in version_str:
            component, version = version_str.split("@", 1)
        elif is_equality:
            # Equality check like context.library == "java" - treat as library filter
            component = version_str  # The library name itself
            version = None
        else:
            # No @ in version string and not equality - might be malformed, skip
            return None
    elif component_type == "agent_version":
        component = "agent"
        version = version_str
    elif component_type == "weblog":
        component = None  # Weblog conditions are handled differently
        version = version_str
    else:
        # Fallback: try to infer component from context
        component = None
        version = version_str

    return {
        "component": component,
        "component_type": component_type,
        "operator": operator,
        "version": version,
        "version_str": version_str,
        "is_equality": is_equality,
    }


def _get_valid_component_names() -> set[str]:
    """Get the set of valid component names that have corresponding manifest files.

    Returns:
        Set of valid component names (e.g., {"python", "java", "nodejs", ...})

    """
    # Valid component names based on existing manifest files in HEAD
    # These should match the actual manifest files in manifests/ directory
    # Only include components that actually have manifest files in the repository
    valid_components = {
        "python",
        "java",
        "nodejs",
        "php",
        "ruby",
        "dotnet",
        "golang",
        "cpp",
        "cpp_nginx",
        "cpp_httpd",
        "rust",
        "agent",
        "python_lambda",
        "python_otel",
        "k8s_cluster_agent",
    }
    return valid_components


def _is_component_name(name: str) -> bool:
    """Check if a name is a component name (like "python", "java") rather than a weblog name.

    Args:
        name: Name to check

    Returns:
        True if it's a component name, False if it's likely a weblog name

    """
    return name.lower() in _get_valid_component_names()


def _is_valid_component(component: str) -> bool:
    """Check if a component name is valid (has a corresponding manifest file).

    Args:
        component: Component name to validate

    Returns:
        True if component is valid, False otherwise

    """
    if not component:
        return False
    return component.lower() in _get_valid_component_names()


def _parse_library_keyword(keywords: dict[str, str]) -> str | None:
    """Extract library name from keywords dict if 'library' key exists."""
    if "library" in keywords:
        # Remove quotes if present
        lib = keywords["library"].strip("\"'")
        return lib
    return None


def _extract_reason(keywords: dict[str, str]) -> str | None:
    """Extract reason from keywords dict if 'reason' key exists."""
    if "reason" in keywords:
        # Remove quotes if present
        reason = keywords["reason"].strip("\"'")
        return reason
    return None


def _parse_weblog_variant_keyword(keywords: dict[str, str]) -> str | None:
    """Extract weblog variant name from keywords dict if 'weblog_variant' key exists."""
    if "weblog_variant" in keywords:
        # Remove quotes if present
        variant = keywords["weblog_variant"].strip("\"'")
        return variant
    return None


def _normalize_version(version: str) -> str:
    """Normalize a version string for manifest entries.

    Rules:
    1. Remove "v" prefix if present (e.g., "v2.1.0" -> "2.1.0")
    2. Separate dev/rc/etc. suffixes from version with "-" instead of "."
       (e.g., "1.1.1.dev" -> "1.1.1-dev", "1.1.1dev" -> "1.1.1-dev")

    Args:
        version: Version string to normalize

    Returns:
        Normalized version string

    """
    if not version:
        return version

    # Remove "v" prefix if present
    if version.startswith("v") or version.startswith("V"):
        version = version[1:]

    # Pattern to match dev/rc/alpha/beta/pre/post suffixes
    # Matches: .dev, .rc, .alpha, .beta, .pre, .post, .a, .b, .rc, etc.
    # Also matches without dot: dev, rc, etc.
    import re

    # Pattern for suffixes with dot: .dev, .rc1, .alpha1, etc.
    pattern_with_dot = r"\.(dev|rc\d*|alpha\d*|beta\d*|pre\d*|post\d*|a\d*|b\d*)(.*)$"
    match = re.search(pattern_with_dot, version, re.IGNORECASE)
    if match:
        suffix = match.group(1) + match.group(2)
        base_version = version[: match.start()]
        return f"{base_version}-{suffix}"

    # Pattern for suffixes without dot: dev, rc1, etc. (at end of string)
    pattern_without_dot = r"([\d.]+)(dev|rc\d*|alpha\d*|beta\d*|pre\d*|post\d*|a\d*|b\d*)(.*)$"
    match = re.search(pattern_without_dot, version, re.IGNORECASE)
    if match:
        base_version = match.group(1)
        suffix = match.group(2) + match.group(3)
        return f"{base_version}-{suffix}"

    return version


def _build_version_spec(operator: str, version: str) -> str:
    """Convert operator and version to a version spec string.

    Examples:
    - ("<", "2.21.0") -> "<2.21.0"
    - (">=", "7.36.0") -> ">=7.36.0"
    - (">=", "v1.1.1.dev") -> ">=1.1.1-dev"

    """
    normalized_version = _normalize_version(version)
    return f"{operator}{normalized_version}"


# Module cache to avoid re-importing the same module multiple times
_module_cache: dict[str, Any] = {}


def _find_child_classes_with_inherited_methods(
    root_dir: str | Path,
    parent_class_name: str,
    method_name: str,
    parent_file: str,
) -> list[tuple[str, str]]:
    """Find all child classes that inherit a method from a parent class.

    Uses Python's import mechanism to inspect actual class hierarchies,
    which is faster and more reliable than AST parsing. Modules are cached
    to avoid re-importing the same module multiple times.

    Args:
        root_dir: Root directory to search (not used, kept for compatibility)
        parent_class_name: Name of the parent class
        method_name: Name of the method to check
        parent_file: File path where parent class is defined

    Returns:
        List of tuples (child_file, child_class_name) for classes that inherit the method

    """
    from pathlib import Path

    child_classes = []

    try:
        # Use AST parsing instead of importing to avoid decorator evaluation issues
        # (decorators may require context to be set up, which isn't available during migration)
        parent_path = Path(parent_file)
        if not parent_path.exists():
            return child_classes

        # Check cache first for this specific lookup
        cache_key = f"{parent_file}:{parent_class_name}:{method_name}"
        if cache_key in _module_cache:
            return _module_cache[cache_key]

        # Read and parse the file using AST (doesn't execute code, so decorators aren't evaluated)
        with open(parent_path, "r", encoding="utf-8") as f:
            source = f.read()

        try:
            tree = ast.parse(source, filename=str(parent_path))
        except SyntaxError:
            # File has syntax errors, skip
            return child_classes

        # Find the parent class definition
        parent_class_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == parent_class_name:
                parent_class_node = node
                break

        if parent_class_node is None:
            return child_classes

        # Check if parent class has the method
        parent_has_method = False
        for item in parent_class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                parent_has_method = True
                break

        if not parent_has_method:
            return child_classes

        # Find all classes that inherit from parent_class_name
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name != parent_class_name:
                # Check if this class inherits from parent_class_name
                inherits_from_parent = False
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == parent_class_name:
                        inherits_from_parent = True
                        break

                if inherits_from_parent:
                    # Check if this class overrides the method
                    overrides_method = False
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                            overrides_method = True
                            break

                    if not overrides_method:
                        # Method is inherited (not overridden)
                        child_classes.append((parent_file, node.name))

        # Cache the result for this specific lookup
        _module_cache[cache_key] = child_classes

    except Exception:
        # If anything goes wrong, return empty list (fail gracefully)
        # This ensures the script continues even if parsing fails
        pass

    return child_classes


def build_manifest_entries(
    decorator_usages: list[DecoratorInfo],
    *,
    component: str | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[DecoratorInfo], int]:
    """Build manifest entries from decorator usage information.

    Args:
        decorator_usages: List of decorator usage dictionaries from find_decorator_usages()
        component: Optional component name to filter by (e.g., "python", "java")

    Returns:
        Tuple of:
        - Dictionary mapping nodeid to list of manifest entry dictionaries.
          Each entry dict contains fields like:
          - declaration: "bug", "missing_feature", or "irrelevant"
          - component_version: version spec string
          - component: component name
          - weblog or excluded_weblog: list of weblog names
          - reason: optional reason string
          - weblog_declaration: dict mapping weblog names to declarations
        - List of successfully migrated decorator usage info (for deletion)
        - Count of unhandled/skipped cases

    """
    manifest_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unhandled_cases: list[dict[str, Any]] = []
    successfully_migrated: list[DecoratorInfo] = []

    def _add_entry_with_inheritance(
        nodeid: str,
        entry: dict[str, Any],
        usage: DecoratorInfo,
        *,
        skip_parent: bool = False,
    ) -> None:
        """Add a manifest entry and also add entries for child classes that inherit the method.

        Args:
            nodeid: Nodeid for the parent class method
            entry: Manifest entry dictionary
            usage: Decorator usage info (contains child class information)
            skip_parent: If True, don't add entry to parent nodeid (already added)

        """
        if not skip_parent:
            manifest_data[nodeid].append(entry)

        # Check if this method is inherited by child classes
        child_classes = usage.get("_child_classes", [])
        parent_class_name = usage.get("class_name")
        method_name = usage["decorated_name"]

        if child_classes and parent_class_name:
            for child_file, child_class_name in child_classes:
                child_nodeid = _build_nodeid(child_file, child_class_name, method_name)

                # Initialize child_nodeid entries if needed
                if child_nodeid not in manifest_data:
                    manifest_data[child_nodeid] = []

                # Check if this is a weblog_declaration entry
                if "weblog_declaration" in entry:
                    # Check if child already has a weblog_declaration entry
                    existing_weblog_decl_entry = None
                    for existing_entry in manifest_data[child_nodeid]:
                        if isinstance(existing_entry, dict) and "weblog_declaration" in existing_entry:
                            # Check if component matches (if present)
                            existing_component = existing_entry.get("component")
                            entry_component = entry.get("component")
                            if existing_component == entry_component:
                                existing_weblog_decl_entry = existing_entry
                                break

                    if existing_weblog_decl_entry:
                        # Merge weblog declarations instead of creating duplicate
                        existing_weblog_decl_entry["weblog_declaration"].update(entry["weblog_declaration"])
                    else:
                        # Create a copy of the entry for the child class
                        child_entry = entry.copy()
                        manifest_data[child_nodeid].append(child_entry)
                else:
                    # For non-weblog_declaration entries, just add a copy
                    child_entry = entry.copy()
                    manifest_data[child_nodeid].append(child_entry)

    def _log_unhandled(reason: str, usage: dict[str, Any], **extra_info: Any) -> None:
        """Log an unhandled case with all available information."""
        unhandled_cases.append(
            {
                "file": usage.get("file"),
                "line": usage.get("lineno"),
                "decorator": usage.get("decorator_base_name"),
                "decorated_type": usage.get("decorated_type"),
                "decorated_name": usage.get("decorated_name"),
                "class_name": usage.get("class_name"),
                "args": usage.get("args", []),
                "keywords": usage.get("keywords", {}),
                "reason": reason,
                **extra_info,
            }
        )

    for usage in decorator_usages:
        # Skip if not a function or class
        if usage["decorated_type"] not in ("function", "async_function", "class"):
            continue

        # Check if this is a method in a parent class that might be inherited
        # If so, we need to create manifest entries for child classes too
        parent_class_name = usage.get("class_name")
        method_name = usage.get("decorated_name")
        parent_file = usage["file"]

        # Only check inheritance for methods (not functions or classes)
        # Also skip if this is already a child class method (we'll handle it via parent)
        if parent_class_name and usage["decorated_type"] in ("function", "async_function"):
            # Find child classes that inherit this method (don't override it)
            child_classes = _find_child_classes_with_inherited_methods(
                "tests/",
                parent_class_name,
                method_name,
                parent_file,
            )

            # Store child classes info for later use
            usage["_child_classes"] = child_classes
        else:
            usage["_child_classes"] = []

        # Build nodeid
        nodeid = _build_nodeid(
            usage["file"],
            usage.get("class_name"),
            usage.get("decorated_name"),
        )

        # Get declaration type from decorator name
        decorator_name = usage.get("decorator_base_name", "")
        if decorator_name not in ("bug", "missing_feature", "irrelevant", "flaky"):
            continue

        declaration = decorator_name

        # Extract reason
        reason = _extract_reason(usage.get("keywords", {}))

        # Parse arguments and keywords
        args = usage.get("args", [])
        keywords = usage.get("keywords", {})

        # Check for library keyword (e.g., library="php")
        library_filter = _parse_library_keyword(keywords)

        # Check for weblog_variant keyword (e.g., weblog_variant="express4")
        weblog_variant_keyword = _parse_weblog_variant_keyword(keywords)

        # If component filter is specified, check if this decorator affects ONLY that component
        if component:
            # Parse condition to determine affected components
            condition_info = None
            if args:
                condition_str = args[0]
                if not _is_complex_condition(condition_str):
                    condition_info = _parse_component_condition(condition_str)

            affected_components = set()

            # Case 1: library keyword (e.g., library="java")
            if library_filter:
                if _is_component_name(library_filter):
                    affected_components.add(library_filter)
                else:
                    # Weblog name, not component - affects all components (for that weblog)
                    # Skip this decorator as it affects multiple/all components
                    continue

            # Case 2: Condition with equality (e.g., context.library == "java")
            if condition_info and condition_info.get("is_equality"):
                operator = condition_info.get("operator")
                # For equality conditions, component is in "component" field, not "component_list"
                component_name = condition_info.get("component")

                if operator == "==":
                    # Affects only the specified component
                    if component_name:
                        if "@" in component_name:
                            base_comp = component_name.split("@")[0]
                        else:
                            base_comp = component_name
                        if _is_valid_component(base_comp):
                            affected_components.add(base_comp)
                elif operator == "!=":
                    # Affects all components EXCEPT the specified one(s)
                    # This means it affects multiple components - skip
                    continue
                elif operator == "in":
                    # Affects multiple components (the ones in the list) - skip
                    continue

            # Case 3: Condition with "in" operator (e.g., context.library in ["java", "python"])
            if (
                condition_info
                and condition_info.get("operator") == "in"
                and condition_info.get("component_type") == "library"
            ):
                # Affects multiple components - skip
                continue

            # Case 4: Condition with version comparison (e.g., context.library < "java@2.0.0")
            if condition_info and condition_info.get("version"):
                component_name = condition_info.get("component")
                if component_name:
                    if "@" in component_name:
                        base_comp = component_name.split("@")[0]
                    else:
                        base_comp = component_name
                    if _is_valid_component(base_comp):
                        affected_components.add(base_comp)

            # Case 5: No library filter and no condition -> affects all components - skip
            if not library_filter and not condition_info:
                continue

            # Check if this decorator affects ONLY the specified component
            if not affected_components:
                # No specific components identified - skip
                continue
            if component not in affected_components:
                # Decorator doesn't affect the specified component - skip
                continue
            if len(affected_components) > 1:
                # Decorator affects multiple components - skip (we only want single-component decorators)
                continue
            # At this point, affected_components == {component}, so we can proceed

        # Parse condition from first positional argument if present
        condition_info = None
        weblog_variant_info = None
        if args:
            # Fail fast: We only handle single positional argument conditions
            if len(args) > 1:
                # Multiple positional arguments - unhandled edge case, skip
                _log_unhandled(
                    "Multiple positional arguments (only single argument conditions are supported)",
                    usage,
                    condition_str=args[0] if args else None,
                    all_args=args,
                )
                continue

            condition_str = args[0]

            # Fail fast: Check for complex conditions (AND/OR) BEFORE parsing
            # If found, skip entirely to avoid partial handling
            if _is_complex_condition(condition_str):
                _log_unhandled(
                    "Complex condition with AND/OR operators (not supported - skipping to avoid partial handling)",
                    usage,
                    condition_str=condition_str,
                )
                continue

            condition_info = _parse_component_condition(condition_str)
            weblog_variant_info = _parse_weblog_variant_condition(condition_str)

            # Fail fast: If we have a condition string but can't parse it properly, skip
            # This handles complex expressions we don't support (e.g., nested conditions)
            if condition_str and not condition_info and not weblog_variant_info:
                # Unparseable condition - skip to avoid unclear entries
                _log_unhandled(
                    "Unparseable condition (complex expressions like nested conditions not supported)",
                    usage,
                    condition_str=condition_str,
                )
                continue

            # Fail fast: If we have a version comparison that's not equality, we need proper parsing
            # Skip this check for "in" operator (handled separately)
            if (
                condition_info
                and not condition_info.get("is_equality")
                and condition_info["component_type"] == "library"
                and condition_info.get("operator") != "in"
            ):
                # Version comparison - check if we have a valid version
                if not condition_info.get("version"):
                    # Invalid version comparison - skip
                    _log_unhandled(
                        "Invalid version comparison (missing version string)",
                        usage,
                        condition_str=condition_str,
                        condition_info=condition_info,
                    )
                    continue

        # Fail fast: If we have both library keyword and condition, this creates ambiguity
        # We can't handle both library keyword and condition simultaneously
        if library_filter and (condition_info or weblog_variant_info):
            # Ambiguous: both library keyword and condition present - unhandled edge case, skip
            _log_unhandled(
                "Ambiguous: both library keyword and condition present (cannot handle both simultaneously)",
                usage,
                library_filter=library_filter,
                condition_info=condition_info,
                weblog_variant_info=weblog_variant_info,
            )
            continue

        # Build manifest entry
        entry: dict[str, Any] = {}

        # Handle complex conditions with both library and weblog_variant
        # These should create weblog_declaration entries
        if condition_info and weblog_variant_info:
            # We have both library and weblog_variant conditions
            # Extract library name from condition_info
            library_name = None
            if condition_info.get("is_equality") and condition_info["component_type"] == "library":
                library_name = condition_info.get("component")
                # Extract base component name (remove version suffix like @2.1.0)
                if library_name and "@" in library_name:
                    library_name = library_name.split("@")[0]
            elif condition_info.get("operator") == "in" and condition_info["component_type"] == "library":
                # Handle "in" operator: extract base component from component_list
                component_list = condition_info.get("component_list", [])
                if component_list:
                    # Get the first component and extract base name
                    first_component = component_list[0]
                    if "@" in first_component:
                        library_name = first_component.split("@")[0]
                    else:
                        library_name = first_component

            # Fail fast: If we have both conditions but can't extract library name, skip
            # This handles cases like version comparisons with weblog_variant (unhandled edge case)
            if not library_name:
                # Can't determine library from condition - skip to avoid unclear entry
                _log_unhandled(
                    "Cannot extract library name from condition (e.g., version comparisons with weblog_variant not supported)",
                    usage,
                    condition_info=condition_info,
                    weblog_variant_info=weblog_variant_info,
                )
                continue

            if library_name:
                # Validate component name - skip if not a valid component
                if not _is_valid_component(library_name):
                    _log_unhandled(
                        f"Invalid component name '{library_name}' (not a valid manifest component)",
                        usage,
                        component=library_name,
                        condition_info=condition_info,
                        weblog_variant_info=weblog_variant_info,
                    )
                    continue

                # Build declaration string
                decl_str = declaration
                if reason:
                    decl_str = f"{declaration} ({reason})"
                # Quote declaration string if it contains special characters
                decl_str = _quote_yaml_value_if_needed(decl_str)

                # Determine which weblogs to include/exclude
                weblog_names = weblog_variant_info.get("weblog_names", [])
                excluded_weblog_names = weblog_variant_info.get("excluded_weblog_names", [])

                # Handle different cases:
                if weblog_names:
                    # Specific weblogs mentioned (e.g., context.weblog_variant == "spring-boot-3-native")
                    # Create weblog_declaration entry
                    if nodeid not in manifest_data:
                        manifest_data[nodeid] = []

                    # Check if there's already a weblog_declaration entry for this nodeid with the same component
                    weblog_decl_entry = None
                    for existing_entry in manifest_data[nodeid]:
                        if "weblog_declaration" in existing_entry:
                            # Only reuse if component matches or is not set yet
                            existing_component = existing_entry.get("component")
                            if existing_component is None or existing_component == library_name:
                                weblog_decl_entry = existing_entry
                                break

                    if weblog_decl_entry is None:
                        weblog_decl_entry = {"component": library_name, "weblog_declaration": {}}
                        manifest_data[nodeid].append(weblog_decl_entry)
                    # Always ensure component is set (in case we're reusing an existing entry)
                    # This must happen AFTER appending to ensure the reference is correct
                    # Note: library_name was already validated above, so it's safe to set here
                    if weblog_decl_entry is not None:
                        weblog_decl_entry["component"] = library_name

                    for weblog_name in weblog_names:
                        weblog_decl_entry["weblog_declaration"][weblog_name] = decl_str
                    successfully_migrated.append(usage)
                    continue
                if excluded_weblog_names:
                    # Excluded weblogs - we can't automatically list all weblogs for a component
                    # So we'll create a simple declaration with component field
                    # The user will need to manually convert this to weblog_declaration with specific weblogs
                    entry["declaration"] = _quote_yaml_value_if_needed(declaration)
                    if reason:
                        entry["reason"] = _quote_yaml_value_if_needed(reason)
                    entry["component"] = library_name
                    # Add excluded_weblog field to indicate which weblogs are excluded
                    # excluded_weblog must be a list[str] according to the manifest parser
                    entry["excluded_weblog"] = excluded_weblog_names
                    _add_entry_with_inheritance(nodeid, entry, usage)
                    successfully_migrated.append(usage)
                    continue
                # No specific weblog conditions, just library - create simple component declaration
                entry["declaration"] = _quote_yaml_value_if_needed(declaration)
                if reason:
                    entry["reason"] = _quote_yaml_value_if_needed(reason)
                entry["component"] = library_name
                _add_entry_with_inheritance(nodeid, entry, usage)
                successfully_migrated.append(usage)
                continue

        # Handle weblog_variant conditions without library conditions
        # (e.g., just context.weblog_variant == "something")
        if weblog_variant_info and not condition_info:
            weblog_names = weblog_variant_info.get("weblog_names", [])
            excluded_weblog_names = weblog_variant_info.get("excluded_weblog_names", [])

            # Fail fast: Weblog variant exclusions without library context are unclear
            # We can't determine which component's weblogs to exclude
            if excluded_weblog_names and not weblog_names:
                # Exclusion without library context - unhandled edge case, skip
                _log_unhandled(
                    "Weblog variant exclusion without library context (cannot determine which component's weblogs to exclude)",
                    usage,
                    weblog_variant_info=weblog_variant_info,
                    excluded_weblog_names=excluded_weblog_names,
                )
                continue

            if weblog_names or excluded_weblog_names:
                if nodeid not in manifest_data:
                    manifest_data[nodeid] = []

                weblog_decl_entry = None
                for existing_entry in manifest_data[nodeid]:
                    if "weblog_declaration" in existing_entry:
                        weblog_decl_entry = existing_entry
                        break

                if weblog_decl_entry is None:
                    # For weblog-only conditions without library, we can't determine component
                    # This case should have been caught earlier, but if we get here, skip
                    _log_unhandled(
                        "Weblog variant condition without library context (cannot determine component)",
                        usage,
                        weblog_variant_info=weblog_variant_info,
                    )
                    continue

                # Ensure component is set if we have library_name
                if library_name and "component" not in weblog_decl_entry:
                    weblog_decl_entry["component"] = library_name

                decl_str = declaration
                if reason:
                    decl_str = f"{declaration} ({reason})"
                # Quote declaration string if it contains special characters
                decl_str = _quote_yaml_value_if_needed(decl_str)

                for weblog_name in weblog_names:
                    weblog_decl_entry["weblog_declaration"][weblog_name] = decl_str

                successfully_migrated.append(usage)
                continue

        # Handle "in" operator for library (e.g., context.library in ["java", "python"])
        if condition_info and condition_info.get("operator") == "in" and condition_info["component_type"] == "library":
            component_list = condition_info.get("component_list", [])
            if component_list:
                # Extract base component names (remove version suffixes like @2.7.2)
                base_components = set()
                for component_name in component_list:
                    # If component name contains @, extract just the base name
                    if "@" in component_name:
                        base_component = component_name.split("@")[0]
                        base_components.add(base_component)
                    else:
                        base_components.add(component_name)

                # Create a declaration entry for each unique base component
                # Filter out invalid components
                valid_components = [c for c in sorted(base_components) if _is_valid_component(c)]
                invalid_components = [c for c in base_components if not _is_valid_component(c)]

                if invalid_components:
                    _log_unhandled(
                        f"Invalid component name(s) in 'in' condition: {invalid_components}",
                        usage,
                        invalid_components=invalid_components,
                        component_list=component_list,
                    )

                if not valid_components:
                    # All components were invalid, skip this decorator
                    continue

                for component_name in valid_components:
                    entry_copy = {
                        "declaration": _quote_yaml_value_if_needed(declaration),
                        "component": component_name,
                    }
                    if reason:
                        entry_copy["reason"] = _quote_yaml_value_if_needed(reason)
                    _add_entry_with_inheritance(nodeid, entry_copy, usage)
                successfully_migrated.append(usage)
                continue

        # Handle equality checks on library (e.g., context.library == "java" or context.library == "cpp_httpd")
        # Also handle negation checks (e.g., context.library != "python")
        if condition_info and condition_info.get("is_equality") and condition_info["component_type"] == "library":
            operator = condition_info.get("operator")
            library_name = condition_info.get("component")

            # Fail fast: If we can't extract library name, skip
            if not library_name:
                # Invalid library equality - skip
                _log_unhandled(
                    "Cannot extract library name from equality condition",
                    usage,
                    condition_info=condition_info,
                )
                continue

            # Extract base component name (remove version suffix like @2.1.0)
            if "@" in library_name:
                library_name = library_name.split("@")[0]

            # Validate component name - skip if not a valid component
            if not _is_valid_component(library_name):
                _log_unhandled(
                    f"Invalid component name '{library_name}' (not a valid manifest component)",
                    usage,
                    component=library_name,
                )
                continue

            # Determine which components to create entries for
            if operator == "==":
                # Equality: create entry only for the specified component
                components_to_create = [library_name]
            elif operator == "!=":
                # Negation: create entries for all valid components EXCEPT the specified one
                valid_components = _get_valid_component_names()
                components_to_create = [c for c in valid_components if c != library_name]
            else:
                # Unknown operator - skip
                _log_unhandled(
                    f"Unknown equality operator '{operator}'",
                    usage,
                    condition_info=condition_info,
                )
                continue

            # Create entries for each component
            for component_name in components_to_create:
                # Skip if component filter is active and doesn't match
                if component and component_name != component:
                    continue

                entry_copy = {
                    "declaration": _quote_yaml_value_if_needed(declaration),
                    "component": component_name,
                }
                if reason:
                    entry_copy["reason"] = _quote_yaml_value_if_needed(reason)

                _add_entry_with_inheritance(nodeid, entry_copy, usage)

            successfully_migrated.append(usage)
            continue

        # Handle library filter (could be component name or weblog name)
        if library_filter:
            # Fail fast: Skip invalid library names (like "not a lib" used in test cases)
            # Valid names should be alphanumeric with hyphens/underscores/dots, no spaces
            library_filter_clean = library_filter.strip()
            if " " in library_filter_clean:
                # Contains spaces - invalid library/weblog name, skip this entry
                _log_unhandled(
                    "Invalid library/weblog name (contains spaces)",
                    usage,
                    library_filter=library_filter,
                )
                continue
            if not library_filter_clean.replace("-", "").replace("_", "").replace(".", "").isalnum():
                # Contains invalid characters - skip this entry
                _log_unhandled(
                    "Invalid library/weblog name (contains invalid characters)",
                    usage,
                    library_filter=library_filter,
                )
                continue

            # Check if library_filter is a component name (like "python", "java")
            # vs an actual weblog name (like "django-poc", "spring-boot")
            if _is_component_name(library_filter):
                # If we also have weblog_variant keyword, create weblog_declaration entry
                if weblog_variant_keyword:
                    if nodeid not in manifest_data:
                        manifest_data[nodeid] = []

                    # Check if there's already a weblog_declaration entry for this nodeid
                    weblog_decl_entry = None
                    for existing_entry in manifest_data[nodeid]:
                        if "weblog_declaration" in existing_entry:
                            existing_component = existing_entry.get("component")
                            if existing_component is None or existing_component == library_filter:
                                weblog_decl_entry = existing_entry
                                break

                    if weblog_decl_entry is None:
                        weblog_decl_entry = {"component": library_filter, "weblog_declaration": {}}
                        manifest_data[nodeid].append(weblog_decl_entry)

                    # Build declaration string
                    decl_str = declaration
                    if reason:
                        decl_str = f"{declaration} ({reason})"
                    # Quote declaration string if it contains special characters
                    decl_str = _quote_yaml_value_if_needed(decl_str)

                    weblog_decl_entry["weblog_declaration"][weblog_variant_keyword] = decl_str
                    # Add entries for child classes that inherit this method
                    # Skip adding to parent since weblog_decl_entry is already in manifest_data[nodeid]
                    _add_entry_with_inheritance(nodeid, weblog_decl_entry, usage, skip_parent=True)
                    successfully_migrated.append(usage)
                    continue

                # This is a component filter without weblog_variant, create a regular declaration with component field
                # Validate component name - skip if not a valid component
                if not _is_valid_component(library_filter):
                    _log_unhandled(
                        f"Invalid component name '{library_filter}' (not a valid manifest component)",
                        usage,
                        component=library_filter,
                    )
                    continue

                entry["declaration"] = _quote_yaml_value_if_needed(declaration)
                if reason:
                    entry["reason"] = _quote_yaml_value_if_needed(reason)
                entry["component"] = library_filter
                _add_entry_with_inheritance(nodeid, entry, usage)
                successfully_migrated.append(usage)
                continue
            # This is a weblog-specific declaration
            # Weblog declarations should NOT include component information
            # We need to group by nodeid and build weblog_declaration structure
            if nodeid not in manifest_data:
                manifest_data[nodeid] = []

            # Check if there's already a weblog_declaration entry for this nodeid
            weblog_decl_entry = None
            for existing_entry in manifest_data[nodeid]:
                if "weblog_declaration" in existing_entry:
                    weblog_decl_entry = existing_entry
                    break

            if weblog_decl_entry is None:
                weblog_decl_entry = {"weblog_declaration": {}}
                manifest_data[nodeid].append(weblog_decl_entry)

            # Build declaration string
            # Note: weblog_declaration entries should NOT include component fields
            decl_str = declaration
            if reason:
                decl_str = f"{declaration} ({reason})"
            # Quote declaration string if it contains special characters
            decl_str = _quote_yaml_value_if_needed(decl_str)

            weblog_decl_entry["weblog_declaration"][library_filter] = decl_str
            # Add entries for child classes that inherit this method
            # Skip adding to parent since weblog_decl_entry is already in manifest_data[nodeid]
            _add_entry_with_inheritance(nodeid, weblog_decl_entry, usage, skip_parent=True)
            # Explicitly ensure no component information is added to weblog_declaration entries
            successfully_migrated.append(usage)
            continue

        if condition_info and condition_info.get("version"):
            # Component version condition (has a version to compare)
            component_name = condition_info["component"]

            # Fail fast: Must have a component name for version conditions
            if not component_name:
                # Version condition without component - unhandled edge case, skip
                _log_unhandled(
                    "Version condition without component name",
                    usage,
                    condition_info=condition_info,
                )
                continue

            if component and component_name and component_name != component:
                continue  # Skip if component filter doesn't match

            entry["declaration"] = declaration
            if reason:
                entry["reason"] = reason

            # Determine component_version based on operator
            operator = condition_info["operator"]
            version = condition_info["version"]

            # Fail fast: Only handle specific operators we understand
            if operator in ("<", "<="):
                # Use component_version (skip if version is less than X)
                entry["component_version"] = _build_version_spec(operator, version)
            elif operator in (">", ">="):
                # This is a component_version (skip if version is greater/equal than X)
                entry["component_version"] = _build_version_spec(operator, version)
            else:
                # Other operators (==, !=) - should have been handled above, skip to be safe
                _log_unhandled(
                    f"Unsupported operator in version condition: {operator}",
                    usage,
                    condition_info=condition_info,
                    operator=operator,
                )
                continue

            # Validate component name - skip if not a valid component
            if not _is_valid_component(component_name):
                _log_unhandled(
                    f"Invalid component name '{component_name}' (not a valid manifest component)",
                    usage,
                    component=component_name,
                    condition_info=condition_info,
                )
                continue

            entry["component"] = component_name
            _add_entry_with_inheritance(nodeid, entry, usage)
            successfully_migrated.append(usage)
            continue

        # Fail fast: If we have any unhandled conditions, skip rather than creating unclear entries
        if condition_info or weblog_variant_info:
            # Unhandled condition type - skip to avoid unclear entry
            _log_unhandled(
                "Unhandled condition type (condition_info or weblog_variant_info present but not processed)",
                usage,
                condition_info=condition_info,
                weblog_variant_info=weblog_variant_info,
            )
            continue

        # Fail fast: If we have library_filter but it wasn't handled above, skip
        if library_filter:
            # Library filter wasn't handled - unhandled edge case, skip
            _log_unhandled(
                "Library filter present but not handled",
                usage,
                library_filter=library_filter,
            )
            continue

        # Simple declaration without conditions
        # Only add if we have component information (otherwise skip - no component to map to)
        if not component:
            # No component information - cannot create manifest entry, skip
            _log_unhandled(
                "No component information available (cannot determine which manifest file to use)",
                usage,
            )
            continue

        entry["declaration"] = declaration
        if reason:
            entry["reason"] = reason
        entry["component"] = component

        manifest_data[nodeid].append(entry)
        successfully_migrated.append(usage)

    # Print unhandled cases summary to stderr
    if unhandled_cases:
        print("\n" + "=" * 80, file=sys.stderr)
        print(f"UNHANDLED CASES SUMMARY: {len(unhandled_cases)} entries skipped", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        for i, case in enumerate(unhandled_cases, 1):
            print(f"\n[{i}] {case['reason']}", file=sys.stderr)
            print(f"    File: {case['file']}", file=sys.stderr)
            print(f"    Line: {case['line']}", file=sys.stderr)
            print(f"    Decorator: {case['decorator']}", file=sys.stderr)
            print(f"    Decorated: {case['decorated_type']} {case['decorated_name']}", file=sys.stderr)
            if case.get("class_name"):
                print(f"    Class: {case['class_name']}", file=sys.stderr)
            if case.get("args"):
                print(f"    Args: {case['args']}", file=sys.stderr)
            if case.get("keywords"):
                print(f"    Keywords: {case['keywords']}", file=sys.stderr)
            # Print additional context
            for key, value in case.items():
                if key not in (
                    "file",
                    "line",
                    "decorator",
                    "decorated_type",
                    "decorated_name",
                    "class_name",
                    "args",
                    "keywords",
                    "reason",
                ):
                    print(f"    {key}: {value}", file=sys.stderr)
        print("\n" + "=" * 80, file=sys.stderr)

    return dict(manifest_data), successfully_migrated, len(unhandled_cases)


def delete_decorators_from_files(successfully_migrated: list[DecoratorInfo]) -> None:
    """Delete decorators from source files that were successfully migrated to manifests.

    Args:
        successfully_migrated: List of decorator usage info that were successfully migrated

    """
    # Group by file to process each file once
    files_to_modify: dict[str, list[DecoratorInfo]] = defaultdict(list)
    for usage in successfully_migrated:
        files_to_modify[usage["file"]].append(usage)

    for filepath, usages in files_to_modify.items():
        try:
            # Read the source file
            with open(filepath, "r", encoding="utf-8") as f:
                source_lines = f.readlines()

            # Read full source for AST parsing
            source = "".join(source_lines)
            try:
                tree = ast.parse(source, filename=filepath)
            except SyntaxError:
                print(f"Warning: Could not parse {filepath}, skipping decorator deletion", file=sys.stderr)
                continue

            # Build a map of nodeid -> list of decorator sources to delete
            decorators_to_delete: dict[tuple[int, int], str] = {}
            for usage in usages:
                lineno = usage["lineno"]
                decorator_index = usage.get("decorator_index")
                decorator_source = usage.get("decorator_source", "")
                if decorator_index is not None and decorator_source:
                    decorators_to_delete[(lineno, decorator_index)] = decorator_source

            # Find lines to delete by visiting AST
            lines_to_delete: set[int] = set()

            def visit_node(node: ast.AST, current_class: str | None = None) -> None:
                """Recursively visit AST nodes to find decorators to delete."""
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    node_lineno = node.lineno
                    for idx, dec in enumerate(node.decorator_list):
                        key = (node_lineno, idx)
                        if key in decorators_to_delete:
                            # Find the line(s) containing this decorator
                            dec_source = decorators_to_delete[key]
                            dec_lines = _find_decorator_lines_by_source(source_lines, node_lineno, dec_source)
                            lines_to_delete.update(dec_lines)

                    # Visit children
                    if isinstance(node, ast.ClassDef):
                        for child in ast.iter_child_nodes(node):
                            visit_node(child, node.name)
                    else:
                        for child in ast.iter_child_nodes(node):
                            visit_node(child, current_class)
                else:
                    # Visit children
                    for child in ast.iter_child_nodes(node):
                        visit_node(child, current_class)

            visit_node(tree)

            # Delete the lines (in reverse order to maintain indices)
            if lines_to_delete:
                # Sort in reverse order
                sorted_lines = sorted(lines_to_delete, reverse=True)
                modified_lines = source_lines[:]
                for line_num in sorted_lines:
                    # Convert to 0-based index
                    idx = line_num - 1
                    if 0 <= idx < len(modified_lines):
                        # Remove the line
                        del modified_lines[idx]
                        # Clean up: if previous line is now empty or only whitespace, consider removing it
                        # But be careful - we don't want to remove too much

                # Write back to file
                with open(filepath, "w", encoding="utf-8") as f:
                    f.writelines(modified_lines)

                print(f"Deleted {len(lines_to_delete)} decorator line(s) from {filepath}", file=sys.stderr)

        except Exception as e:
            print(f"Error processing {filepath}: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            continue


def _find_decorator_lines_by_source(source_lines: list[str], node_lineno: int, decorator_source: str) -> list[int]:
    """Find line numbers that contain the given decorator source.
    Decorators appear on lines before the node definition.

    Args:
        source_lines: List of source file lines
        node_lineno: Line number (1-based) where the decorated node starts
        decorator_source: Source code of the decorator to find

    Returns:
        List of line numbers (1-based) that contain this decorator

    """
    lines: list[int] = []

    # Normalize decorator source for matching
    decorator_clean = decorator_source.strip()
    # Remove leading @ if present for matching
    decorator_without_at = decorator_clean.lstrip("@").strip()

    # Search backwards from node_lineno (decorators appear before the definition)
    # Look back up to 50 lines (should be more than enough)
    for i in range(node_lineno - 1, max(-1, node_lineno - 51), -1):
        if i < 0:
            break
        line_content = source_lines[i].rstrip()

        # Check if this line contains the decorator
        # Match if line contains the decorator source (with or without @)
        if decorator_clean in line_content or decorator_without_at in line_content:
            # Additional check: line should start with @ (it's a decorator)
            if line_content.lstrip().startswith("@"):
                lines.append(i + 1)  # Convert to 1-based
                # Check if decorator spans multiple lines (doesn't end with closing paren)
                # If it does, we need to find the continuation
                if "(" in line_content and not line_content.rstrip().endswith(")"):
                    # Multi-line decorator - continue searching
                    continue
                # Found the decorator line(s)
                break

    return sorted(lines)


def format_manifest_yaml(manifest_data: dict[str, list[dict[str, Any]]]) -> str:
    """Format manifest data as YAML string.

    Args:
        manifest_data: Dictionary mapping nodeid to list of manifest entries

    Returns:
        YAML string representation of the manifest

    """
    try:
        import ruamel.yaml

        use_ruamel = True
    except ImportError:
        import yaml

        use_ruamel = False

    # Sort nodeids alphabetically
    sorted_nodeids = sorted(manifest_data.keys())

    formatted_manifest = {"manifest": {}}

    for nodeid in sorted_nodeids:
        entries = manifest_data[nodeid]

        # If there's only one entry and it's a simple declaration, use inline format
        if len(entries) == 1:
            entry = entries[0]

            # Check if it's a simple inline declaration
            if "weblog_declaration" not in entry and "component_version" not in entry and "component" not in entry:
                # Simple inline format: nodeid: declaration (reason)
                decl = entry.get("declaration", "")
                reason = entry.get("reason")
                if reason:
                    formatted_manifest["manifest"][nodeid] = f"{decl} ({reason})"
                else:
                    formatted_manifest["manifest"][nodeid] = decl
                continue

        # Multi-entry format
        formatted_entries = []
        for entry in entries:
            formatted_entry = {}

            if "weblog_declaration" in entry:
                formatted_entry["weblog_declaration"] = entry["weblog_declaration"]
            else:
                # Format declaration with reason inline: "declaration (reason)"
                if "declaration" in entry:
                    decl = entry["declaration"]
                    reason = entry.get("reason")
                    if reason:
                        formatted_entry["declaration"] = f"{decl} ({reason})"
                    else:
                        formatted_entry["declaration"] = decl
                if "component_version" in entry:
                    formatted_entry["component_version"] = entry["component_version"]
                if "weblog" in entry:
                    formatted_entry["weblog"] = entry["weblog"]
                if "excluded_weblog" in entry:
                    formatted_entry["excluded_weblog"] = entry["excluded_weblog"]

            formatted_entries.append(formatted_entry)

        formatted_manifest["manifest"][nodeid] = formatted_entries

    if use_ruamel:
        yaml_writer = ruamel.yaml.YAML()
        yaml_writer.width = 4096  # Very wide to prevent line breaks
        yaml_writer.preserve_quotes = True
        yaml_writer.default_flow_style = False

        # Use CommentedMap to ensure proper formatting without ? for keys
        from ruamel.yaml.comments import CommentedMap

        cm = CommentedMap(formatted_manifest)

        from io import StringIO

        stream = StringIO()
        yaml_writer.dump(cm, stream)
        output = stream.getvalue()

        # Post-process to ensure nodeids with :: don't get the ? format
        # Replace ? key\n  : value with key: value

        # Pattern to match: ? key\n  : (with 2 spaces before :)
        # This handles both quoted and unquoted keys
        lines = output.split("\n")
        result_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Check if this line starts with ? (complex key indicator)
            if line.strip().startswith("?"):
                # Extract the key (remove ? and leading spaces)
                key = line.strip()[1:].strip()
                # Remove quotes if present
                key = key.strip("\"'")
                # Check if next line starts with '  :' (2 spaces + colon)
                if i + 1 < len(lines) and lines[i + 1].strip().startswith(":"):
                    # Get the value line
                    value_line = lines[i + 1]
                    # Check what comes after the colon
                    colon_pos = value_line.find(":")
                    after_colon = value_line[colon_pos + 1 :].lstrip()

                    # If the value starts with '-', it's a list and should be on next line
                    if after_colon.startswith("-"):
                        result_lines.append(f"  {key}:")
                        # Add the list items with proper indentation (4 spaces for list items)
                        # The value_line has '  : -', we want just '    -' (4 spaces)
                        list_content = value_line[value_line.find("-") :]
                        result_lines.append(f"    {list_content.lstrip()}")
                    # Simple value, can be on same line
                    elif after_colon:
                        result_lines.append(f"  {key}: {after_colon}")
                    else:
                        result_lines.append(f"  {key}:")
                    i += 2
                    continue
            result_lines.append(line)
            i += 1
        output = "\n".join(result_lines)

        return output
    # Fallback to pyyaml with very wide width
    return yaml.dump(
        formatted_manifest,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=4096,  # Very wide to prevent line breaks
    )


def _infer_component_from_weblog(weblog_name: str) -> str | None:
    """Infer component name from weblog name based on common patterns.

    Args:
        weblog_name: Name of the weblog (e.g., "spring-boot", "django-poc", "express4")

    Returns:
        Component name if inference is possible, None otherwise.

    """
    weblog_lower = weblog_name.lower()

    # Java weblogs
    java_patterns = ["spring", "akka", "play", "vertx", "jersey", "ratpack", "resteasy", "quarkus", "tomcat", "jetty"]
    if any(pattern in weblog_lower for pattern in java_patterns):
        return "java"

    # Python weblogs
    python_patterns = ["django", "flask", "fastapi", "bottle", "tornado", "aiohttp", "sanic", "starlette", "cherrypy"]
    if any(pattern in weblog_lower for pattern in python_patterns):
        return "python"

    # Node.js weblogs
    nodejs_patterns = ["express", "koa", "hapi", "next", "nuxt", "fastify", "nest", "sails"]
    if any(pattern in weblog_lower for pattern in nodejs_patterns):
        return "nodejs"

    # PHP weblogs
    php_patterns = ["laravel", "symfony", "slim", "zend", "codeigniter", "cakephp", "yii"]
    if any(pattern in weblog_lower for pattern in php_patterns):
        return "php"

    # Ruby weblogs
    ruby_patterns = ["rails", "sinatra", "grape", "hanami", "padrino"]
    if any(pattern in weblog_lower for pattern in ruby_patterns):
        return "ruby"

    # .NET weblogs
    dotnet_patterns = ["aspnet", "asp-net", "dotnet", ".net"]
    if any(pattern in weblog_lower for pattern in dotnet_patterns):
        return "dotnet"

    # Go weblogs
    golang_patterns = ["gin", "echo", "fiber", "gorilla", "chi", "beego"]
    if any(pattern in weblog_lower for pattern in golang_patterns):
        return "golang"

    # C++ weblogs
    cpp_patterns = ["cpp", "nginx", "httpd", "apache"]
    if any(pattern in weblog_lower for pattern in cpp_patterns):
        if "nginx" in weblog_lower:
            return "cpp_nginx"
        if "httpd" in weblog_lower or "apache" in weblog_lower:
            return "cpp_httpd"
        return "cpp"

    # Rust weblogs
    rust_patterns = ["rust", "actix", "rocket", "warp", "axum"]
    if any(pattern in weblog_lower for pattern in rust_patterns):
        return "rust"

    # Direct component name matches
    component_names = ["java", "python", "nodejs", "php", "ruby", "dotnet", "golang", "cpp", "rust"]
    if weblog_lower in component_names:
        return weblog_lower

    return None


def _extract_component_from_entry(entry: dict[str, Any]) -> str | None:
    """Extract component name from a manifest entry.

    Args:
        entry: Manifest entry dictionary

    Returns:
        Component name if found, None otherwise.

    """
    # Direct component field
    if "component" in entry:
        return entry["component"]

    # Try to infer from weblog_declaration
    if "weblog_declaration" in entry:
        weblog_decl = entry["weblog_declaration"]
        if isinstance(weblog_decl, dict):
            # Get the first weblog name (excluding "*")
            for weblog_name in weblog_decl.keys():
                if weblog_name != "*":
                    inferred = _infer_component_from_weblog(weblog_name)
                    if inferred:
                        return inferred

    return None


def _wrap_key_anchors(content: str) -> str:
    """Wrap anchor references used as keys in quotes for ruamel.yaml parsing.

    Converts lines like:
        *django: v3.12.0.dev
    to:
        '*django': v3.12.0.dev
    """
    import re

    lines = []
    for line in content.splitlines():
        match = re.match(r"^(\s+)(\*[a-zA-Z_][a-zA-Z0-9_]*)(\s*)(:)", line)
        if match:
            indentation = match.group(1)
            anchor_ref = match.group(2)
            spaces_before_colon = match.group(3)
            colon = match.group(4)
            rest_of_line = line[match.end() :]
            lines.append(f"{indentation}'{anchor_ref}'{spaces_before_colon}{colon}{rest_of_line}")
        else:
            lines.append(line)
    return "\n".join(lines)


def _unwrap_key_anchors(content: str) -> str:
    """Unwrap anchor references used as keys, restoring them to unquoted state."""
    import re

    lines = []
    for line in content.splitlines():
        match = re.match(r"^(\s+)(['\"])(\*[a-zA-Z_][a-zA-Z0-9_]*)\2(\s*)(:)", line)
        if match:
            indentation = match.group(1)
            anchor_ref = match.group(3)
            spaces_before_colon = match.group(4)
            colon = match.group(5)
            rest_of_line = line[match.end() :]
            lines.append(f"{indentation}{anchor_ref}{spaces_before_colon}{colon}{rest_of_line}")
        else:
            lines.append(line)
    return "\n".join(lines)


def _normalize_entry_for_comparison(entry: Any) -> dict[str, Any]:
    """Normalize an entry for comparison by converting it to a canonical form."""
    if entry is None:
        return {}
    if not isinstance(entry, dict):
        # Convert non-dict entries (like strings) to dict format
        if isinstance(entry, str):
            return {"declaration": entry}
        return {}
    normalized = {}
    # Sort keys for consistent comparison
    for key in sorted(entry.keys()):
        value = entry[key]
        if isinstance(value, dict):
            # Recursively normalize nested dicts
            normalized[key] = {k: v for k, v in sorted(value.items())}
        elif isinstance(value, list):
            # Sort lists for comparison
            normalized[key] = sorted(value) if all(isinstance(x, (str, int, float)) for x in value) else value
        else:
            normalized[key] = value
    return normalized


def _entry_matches(entry1: Any, entry2: dict[str, Any]) -> bool:
    """Check if two entries are effectively the same."""
    norm1 = _normalize_entry_for_comparison(entry1)
    norm2 = _normalize_entry_for_comparison(entry2)
    return norm1 == norm2


def _convert_excluded_component_version(data: Any) -> Any:
    """Recursively convert excluded_component_version to component_version in manifest data."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == "excluded_component_version":
                # Convert to component_version
                result["component_version"] = _convert_excluded_component_version(value)
            elif key == "manifest" and isinstance(value, dict):
                # Recursively process manifest entries
                result[key] = {}
                for nodeid, entries in value.items():
                    if isinstance(entries, list):
                        result[key][nodeid] = [_convert_excluded_component_version(entry) for entry in entries]
                    else:
                        result[key][nodeid] = _convert_excluded_component_version(entries)
            else:
                result[key] = _convert_excluded_component_version(value)
        return result
    if isinstance(data, list):
        return [_convert_excluded_component_version(item) for item in data]
    return data


def _merge_manifest_entries(
    existing_data: dict[str, Any],
    new_entries: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Merge new manifest entries into existing manifest data.

    Args:
        existing_data: Existing manifest data loaded from YAML
        new_entries: New entries to merge in (nodeid -> list of entries)

    Returns:
        Merged manifest data

    """
    # Ensure manifest section exists
    if "manifest" not in existing_data:
        existing_data["manifest"] = {}

    manifest = existing_data["manifest"]

    # Merge new entries
    for nodeid, entries in new_entries.items():
        if nodeid not in manifest:
            # New nodeid - add all entries
            if len(entries) == 1:
                entry = entries[0]
                # Check if it's a simple inline declaration
                if "weblog_declaration" not in entry and "component_version" not in entry and "component" not in entry:
                    decl = entry.get("declaration", "")
                    reason = entry.get("reason")
                    if reason:
                        manifest[nodeid] = f"{decl} ({reason})"
                    else:
                        manifest[nodeid] = decl
                else:
                    # Convert to list format
                    formatted_entry = {}
                    if "weblog_declaration" in entry:
                        formatted_entry["weblog_declaration"] = entry["weblog_declaration"]
                    if "declaration" in entry:
                        decl = entry["declaration"]
                        reason = entry.get("reason")
                        if reason:
                            formatted_entry["declaration"] = f"{decl} ({reason})"
                        else:
                            formatted_entry["declaration"] = decl
                    if "component_version" in entry:
                        formatted_entry["component_version"] = entry["component_version"]
                    if "weblog" in entry:
                        formatted_entry["weblog"] = entry["weblog"]
                    if "excluded_weblog" in entry:
                        formatted_entry["excluded_weblog"] = entry["excluded_weblog"]
                    manifest[nodeid] = [formatted_entry]
            else:
                # Multiple entries - convert to list format
                formatted_entries = []
                for entry in entries:
                    formatted_entry = {}
                    if "weblog_declaration" in entry:
                        formatted_entry["weblog_declaration"] = entry["weblog_declaration"]
                    if "declaration" in entry:
                        decl = entry["declaration"]
                        reason = entry.get("reason")
                        if reason:
                            formatted_entry["declaration"] = f"{decl} ({reason})"
                        else:
                            formatted_entry["declaration"] = decl
                    if "component_version" in entry:
                        formatted_entry["component_version"] = entry["component_version"]
                    if "weblog" in entry:
                        formatted_entry["weblog"] = entry["weblog"]
                    if "excluded_weblog" in entry:
                        formatted_entry["excluded_weblog"] = entry["excluded_weblog"]
                    formatted_entries.append(formatted_entry)
                manifest[nodeid] = formatted_entries
        else:
            # Existing nodeid - merge entries
            existing_value = manifest[nodeid]

            # Convert existing string to list if needed
            if isinstance(existing_value, str):
                existing_value = [{"declaration": existing_value}]
                manifest[nodeid] = existing_value

            # Ensure it's a list
            if not isinstance(existing_value, list):
                existing_value = [existing_value]
                manifest[nodeid] = existing_value

            # Add new entries that don't already exist
            for new_entry in entries:
                # Format the new entry
                formatted_entry = {}
                if "weblog_declaration" in new_entry:
                    formatted_entry["weblog_declaration"] = new_entry["weblog_declaration"]
                if "declaration" in new_entry:
                    decl = new_entry["declaration"]
                    reason = new_entry.get("reason")
                    if reason:
                        formatted_entry["declaration"] = f"{decl} ({reason})"
                    else:
                        formatted_entry["declaration"] = decl
                if "component_version" in new_entry:
                    formatted_entry["component_version"] = new_entry["component_version"]
                if "weblog" in new_entry:
                    formatted_entry["weblog"] = new_entry["weblog"]
                if "excluded_weblog" in new_entry:
                    formatted_entry["excluded_weblog"] = new_entry["excluded_weblog"]

                # Check if this entry already exists
                entry_exists = False
                for existing_entry in existing_value:
                    if existing_entry is not None and _entry_matches(existing_entry, formatted_entry):
                        entry_exists = True
                        break

                if not entry_exists:
                    existing_value.append(formatted_entry)

    return existing_data


def _extract_existing_nodeids(content: str) -> set[str]:
    """Extract existing nodeids from manifest file content without full parsing.

    This preserves comments by only doing a simple regex match for nodeid patterns.
    """
    import re

    # Pattern to match nodeids: they start with "tests/" and end with ":" or "::"
    # Examples:
    #   tests/path/to/file.py::ClassName::method_name:
    #   tests/path/to/file.py::ClassName:
    #   tests/path/to/file.py:
    pattern = r"^  (tests/[^\s:]+(?:::[^\s:]+)*(?:::)?):"
    nodeids = set()
    for line in content.splitlines():
        match = re.match(pattern, line)
        if match:
            nodeid = match.group(1)
            nodeids.add(nodeid)
    return nodeids


def _quote_yaml_value_if_needed(value: str) -> str:
    """Quote a YAML value if it contains special characters like ":" or "*" that require quoting.

    Args:
        value: String value to potentially quote

    Returns:
        Quoted string if special characters are present, original string otherwise

    """
    if not isinstance(value, str):
        return value

    # If already quoted, check if it needs re-quoting (might have been partially quoted)
    already_quoted = (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))

    # Remove existing quotes for checking
    unquoted_value = value
    if already_quoted:
        unquoted_value = value[1:-1]

    # Check if value contains special characters that require quoting in YAML
    # Focus on ":" and "*" as requested, but also handle other common special chars
    special_chars = [":", "*", "&", "|", "<", ">", "{", "}", "[", "]", "@", "`", "\\", "#", "%", "!", "?", "^"]

    needs_quotes = (
        any(char in unquoted_value for char in special_chars)
        or (unquoted_value.strip() != unquoted_value)  # Leading/trailing whitespace
        or (unquoted_value and unquoted_value[0].isdigit())  # Starts with digit
    )

    if needs_quotes:
        if already_quoted:
            # Already quoted, but might need to escape internal quotes
            if '"' in unquoted_value:
                escaped = unquoted_value.replace('"', '\\"')
                return f'"{escaped}"'
            return value  # Keep existing quotes
        # Escape any existing quotes and wrap in quotes
        escaped = unquoted_value.replace('"', '\\"')
        return f'"{escaped}"'

    return value


def _format_entry_as_yaml(entry_or_list: dict[str, Any] | list[dict[str, Any]], nodeid: str) -> str:
    """Format an entry or list of entries as YAML string for appending to manifest file."""
    try:
        import ruamel.yaml
        from ruamel.yaml import YAML

        use_ruamel = True
    except ImportError:
        import yaml

        use_ruamel = False

    # Determine if it's a single entry or list
    if isinstance(entry_or_list, list):
        entries = entry_or_list
        is_list = True
    else:
        entries = [entry_or_list]
        is_list = False

    entry = entries[0] if entries else {}

    # Check if it's a simple inline declaration (only for single entry)
    is_simple = (
        not is_list
        and "weblog_declaration" not in entry
        and "component_version" not in entry
        and "weblog" not in entry
        and "excluded_weblog" not in entry
        and "declaration" in entry
    )

    if is_simple:
        # Simple inline format: nodeid: declaration (2 spaces for nodeid)
        decl = entry["declaration"]
        # Quote declaration value if it contains special characters
        decl_quoted = _quote_yaml_value_if_needed(decl)
        return f"  {nodeid}: {decl_quoted}"
    # List format: nodeid:\n    - entry (2 spaces for nodeid, 4 spaces for list items)
    if use_ruamel:
        yaml_writer = YAML()
        yaml_writer.width = 10000
        yaml_writer.preserve_quotes = True
        yaml_writer.default_flow_style = False
        yaml_writer.indent(mapping=2, sequence=4, offset=2)
        from io import StringIO

        stream = StringIO()
        yaml_writer.dump({nodeid: entries}, stream)
        output = stream.getvalue().strip()
        # Process lines to ensure correct indentation matching manifest format:
        # - Nodeid line: 2 spaces
        # - List items (-): 4 spaces
        # - Keys in regular entries: 6 spaces
        # - Keys in weblog_declaration: 8 spaces
        # Also handle ? syntax for complex keys (long nodeids)
        lines = output.split("\n")
        result_lines = []
        in_weblog_declaration = False
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.strip().startswith("manifest:") or line.strip().startswith("---"):
                i += 1
                continue
            stripped = line.lstrip()
            if not stripped:
                result_lines.append("")
                i += 1
                continue

            # Handle ? syntax for complex keys (long nodeids)
            # Format: "      ? key\n      :   - item" -> "  key:\n    - item"
            if stripped.startswith("?"):
                # Extract the key (remove ? and any quotes)
                key = stripped[1:].strip().strip("\"'")
                # Check if next line starts with ':'
                if i + 1 < len(lines) and lines[i + 1].strip().startswith(":"):
                    value_line = lines[i + 1]
                    value_stripped = value_line.lstrip()
                    # Get what comes after the colon
                    colon_pos = value_stripped.find(":")
                    after_colon = value_stripped[colon_pos + 1 :].lstrip()

                    # Format as: "  key:" (2 spaces for nodeid)
                    result_lines.append(f"  {key}:")

                    if after_colon.startswith("-"):
                        # List item on same line: "  :   - item" -> "    - item"
                        list_content = after_colon
                        result_lines.append(f"    {list_content}")
                        i += 2  # Skip both ? line and : line
                        continue
                    if after_colon:
                        # Simple value on same line: "  : value" -> "  key: value"
                        result_lines.append(f"  {key}: {after_colon}")
                        i += 2  # Skip both ? line and : line
                        continue
                    # Empty value, check next lines for list items
                    i += 2  # Skip ? and : lines
                    # Process subsequent lines that belong to this entry
                    while i < len(lines):
                        next_line = lines[i]
                        next_stripped = next_line.lstrip()
                        if not next_stripped:
                            i += 1
                            continue
                        # Check if this is still part of the same entry (indented more than 2 spaces)
                        next_indent = len(next_line) - len(next_stripped)
                        if next_indent <= 2 and next_stripped and not next_stripped.startswith(" "):
                            # New top-level entry, stop processing
                            break
                        if next_stripped.startswith("-"):
                            # List item - ensure 4 spaces
                            result_lines.append(f"    {next_stripped}")
                        elif ":" in next_stripped:
                            # Nested key - ensure 6 spaces
                            result_lines.append(f"      {next_stripped}")
                        # Other content - preserve relative indentation but ensure minimum 6 spaces
                        elif next_indent < 6:
                            result_lines.append(f"      {next_stripped}")
                        else:
                            result_lines.append(next_line)
                        i += 1
                    continue
                # Malformed ? syntax, skip
                i += 1
                continue

            current_indent = len(line) - len(stripped)

            # Track if we're inside a weblog_declaration
            if "weblog_declaration" in stripped:
                in_weblog_declaration = True
            elif stripped.startswith("-") and "weblog_declaration" not in stripped:
                in_weblog_declaration = False

            if nodeid in stripped and stripped.endswith(":"):
                # Nodeid line - ensure 2 spaces
                result_lines.append("  " + stripped)
            elif stripped.startswith("-"):
                # List item - ensure 4 spaces
                result_lines.append("    " + stripped)
            elif in_weblog_declaration and ":" in stripped and not stripped.startswith("-"):
                # Keys inside weblog_declaration - ensure 8 spaces
                result_lines.append("        " + stripped)
            elif current_indent >= 6:
                # Already properly indented nested item (6+ spaces, not in weblog_declaration)
                result_lines.append(line)
            elif ":" in stripped and not stripped.startswith("-"):
                # Nested mapping key (not in weblog_declaration) - ensure 6 spaces
                result_lines.append("      " + stripped)
            else:
                # Other lines - preserve as is
                result_lines.append(line)
            i += 1
        return "\n".join(result_lines)
    import yaml

    output = yaml.dump({nodeid: entries}, default_flow_style=False, sort_keys=False, width=4096)
    lines = output.split("\n")
    result_lines = []
    in_weblog_declaration = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("manifest:") or line.strip().startswith("---"):
            i += 1
            continue
        stripped = line.lstrip()
        if not stripped:
            result_lines.append("")
            i += 1
            continue

        # Handle ? syntax for complex keys (long nodeids)
        # Format: "      ? key\n      :   - item" -> "  key:\n    - item"
        if stripped.startswith("?"):
            # Extract the key (remove ? and any quotes)
            key = stripped[1:].strip().strip("\"'")
            # Check if next line starts with ':'
            if i + 1 < len(lines) and lines[i + 1].strip().startswith(":"):
                value_line = lines[i + 1]
                value_stripped = value_line.lstrip()
                # Get what comes after the colon
                colon_pos = value_stripped.find(":")
                after_colon = value_stripped[colon_pos + 1 :].lstrip()

                # Format as: "  key:" (2 spaces for nodeid)
                result_lines.append(f"  {key}:")

                if after_colon.startswith("-"):
                    # List item on same line: "  :   - item" -> "    - item"
                    list_content = after_colon
                    result_lines.append(f"    {list_content}")
                    i += 2  # Skip both ? line and : line
                    continue
                if after_colon:
                    # Simple value on same line: "  : value" -> "  key: value"
                    result_lines.append(f"  {key}: {after_colon}")
                    i += 2  # Skip both ? line and : line
                    continue
                # Empty value, check next lines for list items
                i += 2  # Skip ? and : lines
                # Process subsequent lines that belong to this entry
                while i < len(lines):
                    next_line = lines[i]
                    next_stripped = next_line.lstrip()
                    if not next_stripped:
                        i += 1
                        continue
                    # Check if this is still part of the same entry (indented more than 2 spaces)
                    next_indent = len(next_line) - len(next_stripped)
                    if next_indent <= 2 and next_stripped and not next_stripped.startswith(" "):
                        # New top-level entry, stop processing
                        break
                    if next_stripped.startswith("-"):
                        # List item - ensure 4 spaces
                        result_lines.append(f"    {next_stripped}")
                    elif ":" in next_stripped:
                        # Nested key - ensure 6 spaces
                        result_lines.append(f"      {next_stripped}")
                    # Other content - preserve relative indentation but ensure minimum 6 spaces
                    elif next_indent < 6:
                        result_lines.append(f"      {next_stripped}")
                    else:
                        result_lines.append(next_line)
                    i += 1
                continue
            # Malformed ? syntax, skip
            i += 1
            continue

        current_indent = len(line) - len(stripped)

        # Track if we're inside a weblog_declaration
        if "weblog_declaration" in stripped:
            in_weblog_declaration = True
        elif stripped.startswith("-") and "weblog_declaration" not in stripped:
            in_weblog_declaration = False

        if nodeid in stripped and stripped.endswith(":"):
            # Nodeid line - ensure 2 spaces
            result_lines.append("  " + stripped)
        elif stripped.startswith("-"):
            # List item - ensure 4 spaces
            result_lines.append("    " + stripped)
        elif in_weblog_declaration and ":" in stripped and not stripped.startswith("-"):
            # Keys inside weblog_declaration - ensure 8 spaces
            result_lines.append("        " + stripped)
        elif current_indent >= 6:
            # Already properly indented nested item (6+ spaces, not in weblog_declaration)
            result_lines.append(line)
        elif ":" in stripped and not stripped.startswith("-"):
            # Nested mapping key (not in weblog_declaration) - ensure 6 spaces
            result_lines.append("      " + stripped)
        else:
            # Other lines - preserve as is
            result_lines.append(line)
        i += 1
    return "\n".join(result_lines)


def write_manifest_files_by_component(
    manifest_data: dict[str, list[dict[str, Any]]],
    output_dir: str | Path = "new.manifests",
) -> tuple[dict[str, str], set[str]]:
    """Write manifest entries grouped by component to separate YAML files.
    If files already exist, append new entries at the end to preserve all comments.

    Args:
        manifest_data: Dictionary mapping nodeid to list of manifest entries
        output_dir: Directory to write manifest files to (default: "new.manifests")

    Returns:
        Tuple of:
        - Dictionary mapping component name to file path of written file
        - Set of nodeids that were actually written to manifest files

    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Deduplicate weblog_declaration entries before grouping
    deduplicated_data: dict[str, list[dict[str, Any]]] = {}
    for nodeid, entries in manifest_data.items():
        deduplicated_entries = []
        weblog_decl_entries_by_component: dict[str | None, dict[str, Any]] = {}

        for entry in entries:
            if isinstance(entry, dict) and "weblog_declaration" in entry:
                # Group weblog_declaration entries by component
                component = entry.get("component")
                if component not in weblog_decl_entries_by_component:
                    # First weblog_declaration entry for this component
                    weblog_decl_entries_by_component[component] = entry.copy()
                else:
                    # Merge weblog declarations into existing entry
                    existing_entry = weblog_decl_entries_by_component[component]
                    existing_entry["weblog_declaration"].update(entry["weblog_declaration"])
            else:
                # Non-weblog_declaration entry, add as-is
                deduplicated_entries.append(entry)

        # Add merged weblog_declaration entries
        for merged_entry in weblog_decl_entries_by_component.values():
            deduplicated_entries.append(merged_entry)

        deduplicated_data[nodeid] = deduplicated_entries

    # Group entries by component
    component_manifests: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(dict)

    for nodeid, entries in deduplicated_data.items():
        for entry in entries:
            component = _extract_component_from_entry(entry)

            # If no component found, skip this entry
            if component is None:
                continue

            # Validate component name - skip if not a valid component
            if not _is_valid_component(component):
                print(
                    f"Warning: Skipping entry for invalid component '{component}' (nodeid: {nodeid})", file=sys.stderr
                )
                continue

            # Add entry to component-specific manifest
            if nodeid not in component_manifests[component]:
                component_manifests[component][nodeid] = []
            component_manifests[component][nodeid].append(entry)

    # Write one file per component
    written_files: dict[str, str] = {}
    written_nodeids: set[str] = set()  # Track which nodeids were actually written

    for component, component_data in component_manifests.items():
        if not component_data:
            continue

        filename = f"{component}.yml"
        filepath = output_path / filename

        # Get existing nodeids to avoid duplicates
        existing_nodeids: set[str] = set()
        existing_content = ""
        if filepath.exists():
            existing_content = filepath.read_text(encoding="utf-8")
            existing_nodeids = _extract_existing_nodeids(existing_content)

        # Filter out entries that already exist
        new_entries: dict[str, list[dict[str, Any]]] = {}
        for nodeid, entries in component_data.items():
            if nodeid not in existing_nodeids:
                new_entries[nodeid] = entries

        if not new_entries:
            # No new entries to add
            continue

        # Format new entries BEFORE writing (so we can catch formatting errors)
        new_lines = []
        nodeids_to_write: set[str] = set()  # Track which nodeids we're about to write
        for nodeid, entries in sorted(new_entries.items()):
            # Format entries for this nodeid
            if len(entries) == 1:
                # Single entry - format it
                entry = entries[0]
                formatted_entry = {}
                if "weblog_declaration" in entry:
                    formatted_entry["weblog_declaration"] = entry["weblog_declaration"]
                if "declaration" in entry:
                    decl = entry["declaration"]
                    reason = entry.get("reason")
                    if reason:
                        formatted_entry["declaration"] = f"{decl} ({reason})"
                    else:
                        formatted_entry["declaration"] = decl
                if "component_version" in entry:
                    formatted_entry["component_version"] = entry["component_version"]
                if "weblog" in entry:
                    formatted_entry["weblog"] = entry["weblog"]
                if "excluded_weblog" in entry:
                    formatted_entry["excluded_weblog"] = entry["excluded_weblog"]

                yaml_str = _format_entry_as_yaml(formatted_entry, nodeid)
                if yaml_str:
                    new_lines.append(yaml_str)
                    nodeids_to_write.add(nodeid)
            else:
                # Multiple entries - format as list
                formatted_entries = []
                for entry in entries:
                    formatted_entry = {}
                    if "weblog_declaration" in entry:
                        formatted_entry["weblog_declaration"] = entry["weblog_declaration"]
                    if "declaration" in entry:
                        decl = entry["declaration"]
                        reason = entry.get("reason")
                        if reason:
                            formatted_entry["declaration"] = f"{decl} ({reason})"
                        else:
                            formatted_entry["declaration"] = decl
                    if "component_version" in entry:
                        formatted_entry["component_version"] = entry["component_version"]
                    if "weblog" in entry:
                        formatted_entry["weblog"] = entry["weblog"]
                    if "excluded_weblog" in entry:
                        formatted_entry["excluded_weblog"] = entry["excluded_weblog"]
                    formatted_entries.append(formatted_entry)

                # Format as YAML list
                yaml_str = _format_entry_as_yaml(formatted_entries, nodeid)
                if yaml_str:
                    new_lines.append(yaml_str)
                    nodeids_to_write.add(nodeid)

        # Only add nodeids to written_nodeids AFTER successful write
        try:
            # Append new entries to file
            if filepath.exists():
                # Append mode - preserve all existing content including comments
                with open(filepath, "a", encoding="utf-8") as f:
                    if new_lines:
                        # Ensure there's a newline before adding new entries
                        if not existing_content.endswith("\n"):
                            f.write("\n")
                        f.write("\n".join(new_lines))
                        f.write("\n")
            else:
                # New file - write header and entries
                header = "# yaml-language-server: $schema=https://raw.githubusercontent.com/DataDog/system-tests/refs/heads/main/utils/manifest/schema.json\n---\nmanifest:\n"
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(header)
                    f.write("\n".join(new_lines))
                    f.write("\n")

            # Only add to written_nodeids if write succeeded
            written_nodeids.update(nodeids_to_write)
            written_files[component] = str(filepath)
        except Exception as e:
            # If write fails, don't add nodeids to written_nodeids
            # This ensures decorators aren't deleted if entries weren't successfully written
            print(f"Error writing to {filepath}: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()
            # Continue to next component - don't add failed nodeids to written_nodeids
            continue

    return written_files, written_nodeids


if __name__ == "__main__":
    # Parse arguments
    args = sys.argv[1:]
    manifest_mode = "--manifest" in args
    write_files_mode = "--write-files" in args
    errors_only_mode = "--errors-only" in args or "--unhandled-only" in args

    # Parse --component argument
    component_filter = None
    if "--component" in args:
        component_index = args.index("--component")
        if component_index + 1 < len(args):
            component_filter = args[component_index + 1]
            # Remove --component and its value from args
            args.pop(component_index)
            args.pop(component_index)  # Now the value is at component_index
        else:
            print("Error: --component requires a component name (e.g., --component java)", file=sys.stderr)
            sys.exit(1)

        # Validate component name
        if not _is_valid_component(component_filter):
            print(
                f"Error: Invalid component name '{component_filter}'. Valid components: {', '.join(sorted(_get_valid_component_names()))}",
                file=sys.stderr,
            )
            sys.exit(1)

    if manifest_mode:
        args.remove("--manifest")
    if write_files_mode:
        args.remove("--write-files")
    if errors_only_mode:
        # Remove both possible flag names
        if "--errors-only" in args:
            args.remove("--errors-only")
        if "--unhandled-only" in args:
            args.remove("--unhandled-only")

    # Determine which decorators to process
    all_decorators_mode = "--all" in args
    if all_decorators_mode:
        args.remove("--all")
        # Process all supported decorator types
        decorator_names = ["bug", "missing_feature", "irrelevant", "flaky"]
    else:
        # Default: find bug decorators, or use specified decorator name
        decorator_name = args[0] if args else "bug"
        decorator_names = [decorator_name]

    # Process each decorator type
    all_manifest_data: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_successfully_migrated: list[DecoratorInfo] = []
    total_skipped_count = 0

    for decorator_name in decorator_names:
        usages = find_decorator_usages("tests/", decorator_name)

        if not usages:
            if not all_decorators_mode:
                print(f"No usages of '{decorator_name}' decorator found in tests/", file=sys.stderr)
                sys.exit(1)
            continue

        if manifest_mode or write_files_mode or errors_only_mode:
            # Build manifest entries (this will collect unhandled cases)
            # If component filter is specified, pass it to build_manifest_entries
            manifest_data, successfully_migrated, skipped_count = build_manifest_entries(
                usages, component=component_filter
            )
            total_skipped_count += skipped_count

            # Merge into combined results
            for nodeid, entries in manifest_data.items():
                all_manifest_data[nodeid].extend(entries)
            all_successfully_migrated.extend(successfully_migrated)

            if errors_only_mode:
                # Only show unhandled cases (already printed to stderr by build_manifest_entries)
                # Don't exit even if no manifest entries - we want to show the errors
                continue
            elif len(manifest_data) == 0:
                if not all_decorators_mode:
                    print(f"No manifest entries generated for '{decorator_name}' decorator", file=sys.stderr)
                    sys.exit(1)
                continue
        else:
            # Print detailed usage information
            for u in usages:
                class_info = f" (class: {u['class_name']})" if u.get("class_name") else ""
                print(
                    f"{u['file']}:{u['lineno']} {u['decorated_type']} {u['decorated_name']}{class_info} -> {u['decorator_source']}"
                )
                print("  args:", u["args"])
                print("  kwargs:", u["keywords"])
                print()

    # Write manifest files if in manifest/write mode
    if manifest_mode or write_files_mode:
        if len(all_manifest_data) == 0:
            print(f"No manifest entries generated for decorator(s): {', '.join(decorator_names)}", file=sys.stderr)
            sys.exit(1)

        # Filter by component if specified
        if component_filter:
            filtered_manifest_data: dict[str, list[dict[str, Any]]] = {}
            for nodeid, entries in all_manifest_data.items():
                filtered_entries = []
                for entry in entries:
                    entry_component = _extract_component_from_entry(entry)
                    if entry_component == component_filter:
                        filtered_entries.append(entry)
                if filtered_entries:
                    filtered_manifest_data[nodeid] = filtered_entries

            if len(filtered_manifest_data) == 0:
                print(f"No manifest entries found for component '{component_filter}'", file=sys.stderr)
                sys.exit(1)

            all_manifest_data = filtered_manifest_data
            print(f"Filtering to component: {component_filter}", file=sys.stderr)

        output_dir = "manifests" if manifest_mode else "new.manifests"
        written_files, written_nodeids = write_manifest_files_by_component(all_manifest_data, output_dir=output_dir)

        if written_files:
            print(f"Written {len(written_files)} manifest file(s):", file=sys.stderr)
            for component, filepath in sorted(written_files.items()):
                print(f"  {component}: {filepath}", file=sys.stderr)

            # Only delete decorators for entries that were actually written
            # Filter successfully_migrated to only include decorators for written nodeids
            decorators_to_delete = []
            for usage in all_successfully_migrated:
                # Build nodeid using the same function as in find_decorator_usages
                file_path = usage["file"]
                decorated_name = usage["decorated_name"]
                class_name = usage.get("class_name")

                # Use _build_nodeid to ensure exact match with how nodeids were created
                nodeid = _build_nodeid(file_path, class_name, decorated_name)

                # Check if this nodeid was actually written
                if nodeid in written_nodeids:
                    decorators_to_delete.append(usage)

            # Delete decorators from source files
            if decorators_to_delete:
                delete_decorators_from_files(decorators_to_delete)
        else:
            print("No manifest files written (no entries with component information)", file=sys.stderr)
            sys.exit(1)

        # Print final summary
        print("\n" + "=" * 80, file=sys.stderr)
        print("MIGRATION SUMMARY", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print(f"Total migrated decorators: {len(all_successfully_migrated)}", file=sys.stderr)
        print(f"Total skipped decorators:  {total_skipped_count}", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
