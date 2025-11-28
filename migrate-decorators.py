import ast
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


DecoratorInfo = Dict[str, Any]


def _decorator_name_matches(node: ast.AST, target_name: str) -> bool:
    """
    Check whether a decorator node refers to the given decorator name.

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


def _get_decorator_base_name(node: ast.AST) -> Optional[str]:
    """
    Extract the base name of a decorator (the last attribute / id), if any.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _decorator_call_matches(decorator: ast.expr, target_name: str) -> bool:
    """
    Check if a decorator (which might be a Call or a bare name/attribute)
    matches the target decorator name.
    """
    # @decorator(...)
    if isinstance(decorator, ast.Call):
        return _decorator_name_matches(decorator.func, target_name)

    # @decorator (no call)
    return _decorator_name_matches(decorator, target_name)


def _expr_to_source(expr: ast.AST, source: str) -> str:
    """
    Try to retrieve the exact source code for an expression.
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
    node: Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef],
    decorator: ast.expr,
    filename: str,
    source: str,
    class_name: Optional[str] = None,
) -> DecoratorInfo:
    """
    Build a dictionary with information about one decorator usage on a function or class.
    """
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
    }


def find_decorator_usages(
    root_dir: Union[str, Path],
    decorator_name: str,
    *,
    include_undecorated_calls: bool = False,
) -> List[DecoratorInfo]:
    """
    Recursively scan all .py files under `root_dir` and collect information
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
    results: List[DecoratorInfo] = []

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
        def visit_node(node: ast.AST, current_class: Optional[str] = None) -> None:
            """Recursively visit AST nodes, tracking the current class context."""
            if isinstance(node, ast.ClassDef):
                # Enter a new class context
                for dec in node.decorator_list:
                    if _decorator_call_matches(dec, decorator_name):
                        info = _collect_decorator_info(
                            node=node,
                            decorator=dec,
                            filename=str(path),
                            source=source,
                            class_name=None,  # Classes themselves don't have a parent class
                        )
                        results.append(info)
                # Visit children with this class as the current context
                for child in ast.iter_child_nodes(node):
                    visit_node(child, node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check decorators on functions
                for dec in node.decorator_list:
                    if _decorator_call_matches(dec, decorator_name):
                        info = _collect_decorator_info(
                            node=node,
                            decorator=dec,
                            filename=str(path),
                            source=source,
                            class_name=current_class,
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


def _build_nodeid(file_path: str, class_name: Optional[str], function_name: Optional[str]) -> str:
    """
    Build a pytest nodeid from file path, class name, and function name.
    
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


def _parse_weblog_variant_condition(condition_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse conditions involving context.weblog_variant.
    
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
    pattern3 = r'context\.weblog_variant\s+not\s+in\s+\[([^\]]+)\]'
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
    pattern4a = r'context\.weblog_variant\s+in\s+\[([^\]]+)\]'
    match4a = re.search(pattern4a, condition_str)
    if match4a:
        weblog_list_str = match4a.group(1)
        weblog_names = re.findall(r'"([^"]+)"', weblog_list_str)
        result["weblog_names"].extend(weblog_names)
        result["operator"] = "in"
        return result
    
    # Pattern 4b: context.weblog_variant in ("weblog1", "weblog2")
    pattern4b = r'context\.weblog_variant\s+in\s+\(([^)]+)\)'
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


def _parse_component_condition(condition_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse a condition string like 'context.library < "dotnet@2.21.0"' or
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
    pattern_in_list = r'context\.library\s+in\s+\[([^\]]+)\]'
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
    pattern_in_tuple = r'context\.library\s+in\s+\(([^)]+)\)'
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


def _is_component_name(name: str) -> bool:
    """
    Check if a name is a component name (like "python", "java") rather than a weblog name.
    
    Args:
        name: Name to check
    
    Returns:
        True if it's a component name, False if it's likely a weblog name
    """
    component_names = {
        "python", "java", "nodejs", "php", "ruby", "dotnet", "golang", "go",
        "cpp", "cpp_nginx", "cpp_httpd", "rust", "agent", "python_lambda", "python_otel"
    }
    return name.lower() in component_names


def _parse_library_keyword(keywords: Dict[str, str]) -> Optional[str]:
    """
    Extract library name from keywords dict if 'library' key exists.
    """
    if "library" in keywords:
        # Remove quotes if present
        lib = keywords["library"].strip('"\'')
        return lib
    return None


def _extract_reason(keywords: Dict[str, str]) -> Optional[str]:
    """
    Extract reason from keywords dict if 'reason' key exists.
    """
    if "reason" in keywords:
        # Remove quotes if present
        reason = keywords["reason"].strip('"\'')
        return reason
    return None


def _build_version_spec(operator: str, version: str) -> str:
    """
    Convert operator and version to a version spec string.
    Examples:
    - ("<", "2.21.0") -> "<2.21.0"
    - (">=", "7.36.0") -> ">=7.36.0"
    """
    return f"{operator}{version}"


def build_manifest_entries(
    decorator_usages: List[DecoratorInfo],
    *,
    component: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build manifest entries from decorator usage information.
    
    Args:
        decorator_usages: List of decorator usage dictionaries from find_decorator_usages()
        component: Optional component name to filter by (e.g., "python", "java")
    
    Returns:
        Dictionary mapping nodeid to list of manifest entry dictionaries.
        Each entry dict contains fields like:
        - declaration: "bug", "missing_feature", or "irrelevant"
        - component_version or excluded_component_version: version spec string
        - component: component name
        - weblog or excluded_weblog: list of weblog names
        - reason: optional reason string
        - weblog_declaration: dict mapping weblog names to declarations
    """
    manifest_data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    unhandled_cases: List[Dict[str, Any]] = []
    
    def _log_unhandled(reason: str, usage: Dict[str, Any], **extra_info: Any) -> None:
        """Log an unhandled case with all available information."""
        unhandled_cases.append({
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
        })
    
    for usage in decorator_usages:
        # Skip if not a function or class
        if usage["decorated_type"] not in ("function", "async_function", "class"):
            continue
        
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
            condition_info = _parse_component_condition(condition_str)
            weblog_variant_info = _parse_weblog_variant_condition(condition_str)
            
            # Fail fast: If we have a condition string but can't parse it properly, skip
            # This handles complex expressions we don't support (e.g., 'or' operators, nested conditions)
            if condition_str and not condition_info and not weblog_variant_info:
                # Unparseable condition - skip to avoid unclear entries
                _log_unhandled(
                    "Unparseable condition (complex expressions like 'or' operators or nested conditions not supported)",
                    usage,
                    condition_str=condition_str,
                )
                continue
            
            # Fail fast: If we have a version comparison that's not equality, we need proper parsing
            # Skip this check for "in" operator (handled separately)
            if (condition_info and 
                not condition_info.get("is_equality") and 
                condition_info["component_type"] == "library" and
                condition_info.get("operator") != "in"):
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
        entry: Dict[str, Any] = {}
        
        # Handle complex conditions with both library and weblog_variant
        # These should create weblog_declaration entries
        if condition_info and weblog_variant_info:
            # We have both library and weblog_variant conditions
            # Extract library name from condition_info
            library_name = None
            if condition_info.get("is_equality") and condition_info["component_type"] == "library":
                library_name = condition_info.get("component")
            
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
                # Build declaration string
                decl_str = declaration
                if reason:
                    decl_str = f"{declaration} ({reason})"
                
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
                    if weblog_decl_entry is not None:
                        weblog_decl_entry["component"] = library_name
                    
                    for weblog_name in weblog_names:
                        weblog_decl_entry["weblog_declaration"][weblog_name] = decl_str
                    continue
                elif excluded_weblog_names:
                    # Excluded weblogs - we can't automatically list all weblogs for a component
                    # So we'll create a simple declaration with component field
                    # The user will need to manually convert this to weblog_declaration with specific weblogs
                    entry["declaration"] = declaration
                    if reason:
                        entry["reason"] = reason
                    entry["component"] = library_name
                    # Add excluded_weblog field to indicate which weblogs are excluded
                    # excluded_weblog must be a list[str] according to the manifest parser
                    entry["excluded_weblog"] = excluded_weblog_names
                    manifest_data[nodeid].append(entry)
                    continue
                else:
                    # No specific weblog conditions, just library - create simple component declaration
                    entry["declaration"] = declaration
                    if reason:
                        entry["reason"] = reason
                    entry["component"] = library_name
                    manifest_data[nodeid].append(entry)
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
                
                for weblog_name in weblog_names:
                    weblog_decl_entry["weblog_declaration"][weblog_name] = decl_str
                
                continue
        
        # Handle "in" operator for library (e.g., context.library in ["java", "python"])
        if condition_info and condition_info.get("operator") == "in" and condition_info["component_type"] == "library":
            component_list = condition_info.get("component_list", [])
            if component_list:
                # Create a declaration entry for each component in the list
                for component_name in component_list:
                    entry_copy = {
                        "declaration": declaration,
                        "component": component_name,
                    }
                    if reason:
                        entry_copy["reason"] = reason
                    manifest_data[nodeid].append(entry_copy)
                continue
        
        # Handle equality checks on library (e.g., context.library == "java" or context.library == "cpp_httpd")
        # These should be treated as simple declarations with component field
        if condition_info and condition_info.get("is_equality") and condition_info["component_type"] == "library":
            # For equality checks, create a declaration with component field
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
            
            entry["declaration"] = declaration
            if reason:
                entry["reason"] = reason
            entry["component"] = library_name
            manifest_data[nodeid].append(entry)
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
                # This is a component filter, create a regular declaration with component field
                entry["declaration"] = declaration
                if reason:
                    entry["reason"] = reason
                entry["component"] = library_filter
                manifest_data[nodeid].append(entry)
                continue
            else:
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
                
                weblog_decl_entry["weblog_declaration"][library_filter] = decl_str
                # Explicitly ensure no component information is added to weblog_declaration entries
                continue
            
        elif condition_info and condition_info.get("version"):
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
            
            # Determine if this is excluded_component_version or component_version
            operator = condition_info["operator"]
            version = condition_info["version"]
            
            # Fail fast: Only handle specific operators we understand
            if operator in ("<", "<="):
                # This is an excluded_component_version (skip if version is less than X)
                entry["excluded_component_version"] = _build_version_spec(operator, version)
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
            
            entry["component"] = component_name
            manifest_data[nodeid].append(entry)
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
        entry["declaration"] = declaration
        if reason:
            entry["reason"] = reason
        
        if component:
            entry["component"] = component
        
        manifest_data[nodeid].append(entry)
    
    # Print unhandled cases summary to stderr
    if unhandled_cases:
        print("\n" + "="*80, file=sys.stderr)
        print(f"UNHANDLED CASES SUMMARY: {len(unhandled_cases)} entries skipped", file=sys.stderr)
        print("="*80, file=sys.stderr)
        for i, case in enumerate(unhandled_cases, 1):
            print(f"\n[{i}] {case['reason']}", file=sys.stderr)
            print(f"    File: {case['file']}", file=sys.stderr)
            print(f"    Line: {case['line']}", file=sys.stderr)
            print(f"    Decorator: {case['decorator']}", file=sys.stderr)
            print(f"    Decorated: {case['decorated_type']} {case['decorated_name']}", file=sys.stderr)
            if case.get('class_name'):
                print(f"    Class: {case['class_name']}", file=sys.stderr)
            if case.get('args'):
                print(f"    Args: {case['args']}", file=sys.stderr)
            if case.get('keywords'):
                print(f"    Keywords: {case['keywords']}", file=sys.stderr)
            # Print additional context
            for key, value in case.items():
                if key not in ('file', 'line', 'decorator', 'decorated_type', 'decorated_name', 
                              'class_name', 'args', 'keywords', 'reason'):
                    print(f"    {key}: {value}", file=sys.stderr)
        print("\n" + "="*80, file=sys.stderr)
    
    return dict(manifest_data)


def format_manifest_yaml(manifest_data: Dict[str, List[Dict[str, Any]]]) -> str:
    """
    Format manifest data as YAML string.
    
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
            if "weblog_declaration" not in entry and "component_version" not in entry and "excluded_component_version" not in entry and "component" not in entry:
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
                # Also include component if present
                if "component" in entry:
                    formatted_entry["component"] = entry["component"]
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
                if "excluded_component_version" in entry:
                    formatted_entry["excluded_component_version"] = entry["excluded_component_version"]
                if "component" in entry:
                    formatted_entry["component"] = entry["component"]
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
        import re
        # Pattern to match: ? key\n  : (with 2 spaces before :)
        # This handles both quoted and unquoted keys
        lines = output.split('\n')
        result_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Check if this line starts with ? (complex key indicator)
            if line.strip().startswith('?'):
                # Extract the key (remove ? and leading spaces)
                key = line.strip()[1:].strip()
                # Remove quotes if present
                key = key.strip('"\'')
                # Check if next line starts with '  :' (2 spaces + colon)
                if i + 1 < len(lines) and lines[i + 1].strip().startswith(':'):
                    # Get the value line
                    value_line = lines[i + 1]
                    # Check what comes after the colon
                    colon_pos = value_line.find(':')
                    after_colon = value_line[colon_pos + 1:].lstrip()
                    
                    # If the value starts with '-', it's a list and should be on next line
                    if after_colon.startswith('-'):
                        result_lines.append(f"  {key}:")
                        # Add the list items with proper indentation (4 spaces for list items)
                        # The value_line has '  : -', we want just '    -' (4 spaces)
                        list_content = value_line[value_line.find('-'):]
                        result_lines.append(f"    {list_content.lstrip()}")
                    else:
                        # Simple value, can be on same line
                        if after_colon:
                            result_lines.append(f"  {key}: {after_colon}")
                        else:
                            result_lines.append(f"  {key}:")
                    i += 2
                    continue
            result_lines.append(line)
            i += 1
        output = '\n'.join(result_lines)
        
        return output
    else:
        # Fallback to pyyaml with very wide width
        return yaml.dump(
            formatted_manifest,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=4096,  # Very wide to prevent line breaks
        )


def _infer_component_from_weblog(weblog_name: str) -> Optional[str]:
    """
    Infer component name from weblog name based on common patterns.
    
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
        elif "httpd" in weblog_lower or "apache" in weblog_lower:
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


def _extract_component_from_entry(entry: Dict[str, Any]) -> Optional[str]:
    """
    Extract component name from a manifest entry.
    
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


def write_manifest_files_by_component(
    manifest_data: Dict[str, List[Dict[str, Any]]],
    output_dir: Union[str, Path] = "new.manifests",
) -> Dict[str, str]:
    """
    Write manifest entries grouped by component to separate YAML files.
    
    Args:
        manifest_data: Dictionary mapping nodeid to list of manifest entries
        output_dir: Directory to write manifest files to (default: "new.manifests")
    
    Returns:
        Dictionary mapping component name to file path of written file.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Group entries by component
    component_manifests: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: {})
    
    for nodeid, entries in manifest_data.items():
        for entry in entries:
            component = _extract_component_from_entry(entry)
            
            # If no component found, skip this entry (or put in "general" file)
            # For now, we'll skip entries without a component
            if component is None:
                continue
            
            # Add entry to component-specific manifest
            if nodeid not in component_manifests[component]:
                component_manifests[component][nodeid] = []
            component_manifests[component][nodeid].append(entry)
    
    # Write one file per component
    written_files: Dict[str, str] = {}
    
    for component, component_data in component_manifests.items():
        if not component_data:
            continue
        
        # Format YAML for this component
        yaml_content = format_manifest_yaml(component_data)
        
        # Write to file
        filename = f"{component}.yml"
        filepath = output_path / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(yaml_content)
        
        written_files[component] = str(filepath)
    
    return written_files


if __name__ == "__main__":
    import sys
    
    # Parse arguments
    args = sys.argv[1:]
    manifest_mode = "--manifest" in args
    write_files_mode = "--write-files" in args
    errors_only_mode = "--errors-only" in args or "--unhandled-only" in args
    
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
    
    # Default: find bug decorators
    decorator_name = args[0] if args else "bug"
    
    usages = find_decorator_usages("tests/", decorator_name)
    
    if not usages:
        print(f"No usages of '{decorator_name}' decorator found in tests/", file=sys.stderr)
        sys.exit(1)
    
    if manifest_mode or write_files_mode or errors_only_mode:
        # Build manifest entries (this will collect unhandled cases)
        manifest_data = build_manifest_entries(usages)
        
        if errors_only_mode:
            # Only show unhandled cases (already printed to stderr by build_manifest_entries)
            # Don't exit even if no manifest entries - we want to show the errors
            pass
        elif len(manifest_data) == 0:
            print(f"No manifest entries generated for '{decorator_name}' decorator", file=sys.stderr)
            sys.exit(1)
        elif write_files_mode:
            # Write files grouped by component
            written_files = write_manifest_files_by_component(manifest_data)
            if written_files:
                print(f"Written {len(written_files)} manifest file(s):", file=sys.stderr)
                for component, filepath in sorted(written_files.items()):
                    print(f"  {component}: {filepath}", file=sys.stderr)
            else:
                print(f"No manifest files written (no entries with component information)", file=sys.stderr)
                sys.exit(1)
        elif manifest_mode:
            # Print manifest entries as YAML
            yaml_output = format_manifest_yaml(manifest_data)
            print(yaml_output)
    else:
        # Print detailed usage information
        for u in usages:
            class_info = f" (class: {u['class_name']})" if u.get("class_name") else ""
            print(f"{u['file']}:{u['lineno']} {u['decorated_type']} {u['decorated_name']}{class_info} -> {u['decorator_source']}")
            print("  args:", u["args"])
            print("  kwargs:", u["keywords"])
            print()
