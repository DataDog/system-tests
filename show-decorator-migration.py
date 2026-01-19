#!/usr/bin/env python3
"""Show decorators removed in current branch compared to main and their corresponding manifest entries.

This script compares the current branch with main to find decorators that were removed
and shows the corresponding manifest entries side by side for manual verification.
"""

import ast
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def _decorator_name_matches(node: ast.AST, target_name: str) -> bool:
    """Check whether a decorator node refers to the given decorator name."""
    if isinstance(node, ast.Name):
        return node.id == target_name
    if isinstance(node, ast.Attribute):
        return _decorator_name_matches(
            node.attr if isinstance(node.attr, ast.AST) else ast.Name(id=node.attr), target_name
        ) or (node.attr == target_name)
    return False


def _decorator_call_matches(decorator: ast.expr, target_name: str) -> bool:
    """Check if a decorator matches the target decorator name."""
    if isinstance(decorator, ast.Call):
        return _decorator_name_matches(decorator.func, target_name)
    return _decorator_name_matches(decorator, target_name)


def _get_decorator_base_name(node: ast.AST) -> str | None:
    """Extract the base name of a decorator."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _expr_to_source(expr: ast.AST, source: str) -> str:
    """Try to retrieve the exact source code for an expression."""
    try:
        segment = ast.get_source_segment(source, expr)
        if segment is not None:
            return segment
    except Exception:
        pass

    if isinstance(expr, ast.Constant):
        return repr(expr.value)
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return f"{_expr_to_source(expr.value, source)}.{expr.attr}"
    return ast.dump(expr)


def _build_nodeid(file_path: str, class_name: str | None, function_name: str | None) -> str:
    """Build a pytest nodeid from file path, class name, and function name."""
    if class_name and function_name:
        return f"{file_path}::{class_name}::{function_name}"
    if function_name:
        return f"{file_path}::{function_name}"
    if class_name:
        return f"{file_path}::{class_name}"
    return file_path


def find_decorators_in_file(
    file_path: Path, decorator_names: list[str], actual_file_path: str | None = None
) -> list[dict[str, Any]]:
    """Find all decorators in a file."""
    results = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, filename=str(file_path))

        # Use a visitor pattern to maintain class context
        def visit_node(node: ast.AST, current_class: str | None = None):
            if isinstance(node, ast.ClassDef):
                # Process class-level decorators
                for dec in node.decorator_list:
                    for decorator_name in decorator_names:
                        if _decorator_call_matches(dec, decorator_name):
                            decorator_source = _expr_to_source(dec, source)
                            nodeid = _build_nodeid(actual_file_path or str(file_path), node.name, None)
                            results.append(
                                {
                                    "file": actual_file_path or str(file_path),
                                    "lineno": dec.lineno,
                                    "nodeid": nodeid,
                                    "class_name": node.name,
                                    "function_name": None,
                                    "decorator_name": decorator_name,
                                    "decorator_source": decorator_source,
                                    "line_content": source.split("\n")[dec.lineno - 1]
                                    if dec.lineno <= len(source.split("\n"))
                                    else "",
                                }
                            )

                # Process methods in this class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for dec in item.decorator_list:
                            for decorator_name in decorator_names:
                                if _decorator_call_matches(dec, decorator_name):
                                    decorator_source = _expr_to_source(dec, source)
                                    nodeid = _build_nodeid(actual_file_path or str(file_path), node.name, item.name)
                                    results.append(
                                        {
                                            "file": actual_file_path or str(file_path),
                                            "lineno": dec.lineno,
                                            "nodeid": nodeid,
                                            "class_name": node.name,
                                            "function_name": item.name,
                                            "decorator_name": decorator_name,
                                            "decorator_source": decorator_source,
                                            "line_content": source.split("\n")[dec.lineno - 1]
                                            if dec.lineno <= len(source.split("\n"))
                                            else "",
                                        }
                                    )
                        # Visit nested functions
                        for child in ast.iter_child_nodes(item):
                            visit_node(child, node.name)

                # Visit nested classes
                for item in node.body:
                    if isinstance(item, ast.ClassDef):
                        visit_node(item, None)  # Nested class, reset context
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Top-level function (not in a class)
                for dec in node.decorator_list:
                    for decorator_name in decorator_names:
                        if _decorator_call_matches(dec, decorator_name):
                            decorator_source = _expr_to_source(dec, source)
                            nodeid = _build_nodeid(actual_file_path or str(file_path), None, node.name)
                            results.append(
                                {
                                    "file": actual_file_path or str(file_path),
                                    "lineno": dec.lineno,
                                    "nodeid": nodeid,
                                    "class_name": None,
                                    "function_name": node.name,
                                    "decorator_name": decorator_name,
                                    "decorator_source": decorator_source,
                                    "line_content": source.split("\n")[dec.lineno - 1]
                                    if dec.lineno <= len(source.split("\n"))
                                    else "",
                                }
                            )
            else:
                # Visit children
                for child in ast.iter_child_nodes(node):
                    visit_node(child, current_class)

        visit_node(tree)
    except Exception as e:
        print(f"Error parsing {file_path}: {e}", file=sys.stderr)

    return results


def get_decorators_from_branch(
    branch: str, decorator_names: list[str], root_dir: Path = Path("tests/")
) -> dict[str, list[dict[str, Any]]]:
    """Get all decorators from a specific branch, indexed by nodeid."""
    decorators_by_nodeid = defaultdict(list)

    # Get list of Python files in tests/ directory from the branch
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", branch, str(root_dir)],
        check=False,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )

    if result.returncode != 0:
        print(f"Error getting file list from {branch}: {result.stderr}", file=sys.stderr)
        return decorators_by_nodeid

    python_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]

    for file_path_str in python_files:
        file_path = Path(file_path_str)

        # Get file content from branch
        result = subprocess.run(
            ["git", "show", f"{branch}:{file_path_str}"], check=False, capture_output=True, text=True, cwd=Path.cwd()
        )

        if result.returncode != 0:
            continue

        # Write to temp file and parse
        temp_file = Path("/tmp") / f"temp_{file_path.name}"
        try:
            temp_file.write_text(result.stdout, encoding="utf-8")
            # Pass the actual file path so nodeids are built correctly
            decorators = find_decorators_in_file(temp_file, decorator_names, actual_file_path=file_path_str)

            for dec in decorators:
                decorators_by_nodeid[dec["nodeid"]].append(dec)
        finally:
            if temp_file.exists():
                temp_file.unlink()

    return decorators_by_nodeid


def load_manifest_entries(manifest_dir: Path = Path("manifests/")) -> dict[str, list[dict[str, Any]]]:
    """Load manifest entries from YAML files."""
    import yaml

    manifest_entries = defaultdict(list)

    if not manifest_dir.exists():
        return manifest_entries

    for manifest_file in manifest_dir.glob("*.yml"):
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "manifest" not in data:
                continue

            component = manifest_file.stem

            for nodeid, entries in data["manifest"].items():
                if isinstance(entries, list):
                    for entry in entries:
                        manifest_entries[nodeid].append(
                            {
                                "component": component,
                                "nodeid": nodeid,
                                "entry": entry,
                            }
                        )
                else:
                    # Single entry (string or dict)
                    manifest_entries[nodeid].append(
                        {
                            "component": component,
                            "nodeid": nodeid,
                            "entry": entries,
                        }
                    )
        except Exception as e:
            print(f"Error loading {manifest_file}: {e}", file=sys.stderr)

    return manifest_entries


def format_decorator(dec: dict[str, Any], max_width: int = 75) -> list[str]:
    """Format a decorator for display, returns list of lines."""
    lines = []
    lines.append(f"File: {dec['file']}")
    lines.append(f"Line: {dec['lineno']}")
    lines.append(f"NodeID: {dec['nodeid']}")
    lines.append("")
    lines.append("Decorator:")
    lines.append(f"  {dec['decorator_source']}")

    # Wrap long lines
    formatted_lines = []
    for line in lines:
        if len(line) > max_width and not line.startswith("  "):
            # Simple wrapping for non-indented lines
            words = line.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 > max_width:
                    if current_line:
                        formatted_lines.append(current_line)
                    current_line = word
                else:
                    current_line += (" " if current_line else "") + word
            if current_line:
                formatted_lines.append(current_line)
        else:
            formatted_lines.append(line)

    return formatted_lines


def format_manifest_entry(entry_data: dict[str, Any], max_width: int = 75) -> list[str]:
    """Format a manifest entry for display, returns list of lines."""
    import yaml

    lines = []
    lines.append(f"Component: {entry_data['component']}")
    lines.append(f"NodeID: {entry_data['nodeid']}")
    lines.append("")
    lines.append("Entry:")

    # Format entry as YAML
    entry = entry_data["entry"]
    try:
        yaml_str = yaml.dump(entry, default_flow_style=False, sort_keys=False, width=max_width)
        # Indent YAML content
        for yaml_line in yaml_str.strip().split("\n"):
            lines.append(f"  {yaml_line}")
    except Exception as e:
        lines.append(f"  {entry}")
        lines.append(f"  (Error formatting: {e})")

    return lines


def main():
    """Main function."""
    decorator_names = ["bug", "missing_feature", "irrelevant", "flaky"]

    print("=" * 160)
    print("DECORATOR MIGRATION COMPARISON")
    print("=" * 160)
    print("\nComparing current branch with 'main' branch...")
    print("Finding decorators removed in current branch and their manifest entries...\n")

    # Get decorators from main branch
    print("Loading decorators from 'main' branch...", file=sys.stderr)
    main_decorators = get_decorators_from_branch("main", decorator_names)

    # Get decorators from current branch (HEAD)
    print("Loading decorators from current branch (HEAD)...", file=sys.stderr)
    current_decorators = get_decorators_from_branch("HEAD", decorator_names)

    # Find decorators that exist in main but not in current branch
    removed_decorators = {}
    for nodeid, decs in main_decorators.items():
        if nodeid not in current_decorators:
            # Entire nodeid removed - all decorators for this nodeid were removed
            removed_decorators[nodeid] = decs
        else:
            # Nodeid still exists - check if specific decorators were removed
            # Compare by decorator source (normalized to handle whitespace differences)
            def normalize_decorator(dec):
                # Normalize whitespace for comparison
                source = dec["decorator_source"].strip()
                # Remove extra spaces
                source = " ".join(source.split())
                return source

            main_decorator_normalized = {normalize_decorator(dec): dec for dec in decs}
            current_decorator_normalized = {normalize_decorator(dec): dec for dec in current_decorators[nodeid]}

            removed_normalized = set(main_decorator_normalized.keys()) - set(current_decorator_normalized.keys())
            if removed_normalized:
                removed_decorators[nodeid] = [main_decorator_normalized[norm] for norm in removed_normalized]

    if not removed_decorators:
        print("\nNo decorators were removed in the current branch compared to main.")
        return

    # Load manifest entries from current branch
    print("Loading manifest entries from current branch...", file=sys.stderr)
    manifest_entries = load_manifest_entries()

    # Match removed decorators with manifest entries
    matched_pairs = []
    unmatched_decorators = []

    # Debug: show some sample nodeids for comparison
    if removed_decorators:
        print("\nDebug: Sample removed decorator nodeids (first 5):", file=sys.stderr)
        for i, nodeid in enumerate(list(removed_decorators.keys())[:5]):
            print(f"  {i + 1}. {nodeid}", file=sys.stderr)

        if manifest_entries:
            print("\nDebug: Sample manifest entry nodeids (first 5):", file=sys.stderr)
            for i, nodeid in enumerate(list(manifest_entries.keys())[:5]):
                print(f"  {i + 1}. {nodeid}", file=sys.stderr)

    for nodeid, decs in removed_decorators.items():
        if nodeid in manifest_entries:
            matched_pairs.append((decs, manifest_entries[nodeid]))
        else:
            # Try to find partial matches (maybe nodeid format differs slightly)
            # Check if any manifest nodeid starts with the same file path
            file_path = nodeid.split("::")[0] if "::" in nodeid else nodeid
            partial_matches = [nid for nid in manifest_entries.keys() if nid.startswith(file_path)]

            if partial_matches:
                # Store with partial match info for debugging
                unmatched_decorators.append((nodeid, decs, partial_matches))
            else:
                unmatched_decorators.append((nodeid, decs, []))

    # Display results
    print(f"\nFound {len(removed_decorators)} nodeid(s) with removed decorators")
    print(f"  - {len(matched_pairs)} matched with manifest entries")
    print(f"  - {len(unmatched_decorators)} without manifest entries\n")

    # Display matched pairs side by side
    if matched_pairs:
        print("=" * 160)
        print("MATCHED: REMOVED DECORATORS ↔ MANIFEST ENTRIES")
        print("=" * 160)

        for idx, (decs, entries) in enumerate(matched_pairs, 1):
            print(f"\n{'═' * 160}")
            print(f"MATCH {idx}/{len(matched_pairs)}")
            print(f"{'═' * 160}\n")

            # Extract and display nodeids aligned
            for i, dec in enumerate(decs, 1):
                if i > 1:
                    print()
                    print("─" * 160)
                    print()

                # Find corresponding manifest entry (by nodeid)
                dec_nodeid = dec["nodeid"]
                matching_entries = [e for e in entries if e["nodeid"] == dec_nodeid]

                if not matching_entries:
                    # No exact match, use first entry
                    matching_entries = entries[:1] if entries else []

                entry_data = matching_entries[0] if matching_entries else None

                # Display nodeids aligned at the top
                print("NODEID COMPARISON:")
                print("─" * 160)
                if entry_data:
                    entry_nodeid = entry_data["nodeid"]
                    # Align nodeids directly above each other
                    max_nodeid_len = max(len(dec_nodeid), len(entry_nodeid))
                    print("REMOVED DECORATOR".ljust(80) + "│" + "MANIFEST ENTRY".ljust(80))
                    print("─" * 80 + "┼" + "─" * 80)
                    print(dec_nodeid.ljust(80) + "│" + entry_nodeid.ljust(80))

                    # Highlight differences character by character
                    if dec_nodeid != entry_nodeid:
                        print()
                        print("⚠️  WARNING: NodeIDs differ!")
                        # Show character-by-character comparison
                        diff_lines = []
                        for i in range(max(len(dec_nodeid), len(entry_nodeid))):
                            dec_char = dec_nodeid[i] if i < len(dec_nodeid) else " "
                            entry_char = entry_nodeid[i] if i < len(entry_nodeid) else " "
                            if dec_char != entry_char:
                                diff_lines.append(f"  Position {i}: '{dec_char}' vs '{entry_char}'")
                        if diff_lines:
                            for diff_line in diff_lines[:5]:  # Show first 5 differences
                                print(diff_line)
                            if len(diff_lines) > 5:
                                print(f"  ... and {len(diff_lines) - 5} more differences")
                else:
                    print("REMOVED DECORATOR".ljust(80) + "│" + "MANIFEST ENTRY".ljust(80))
                    print("─" * 80 + "┼" + "─" * 80)
                    print(dec_nodeid.ljust(80) + "│" + "(no match)".ljust(80))
                print()

                # Display declarations aligned
                print("DECLARATION COMPARISON:")
                print("─" * 160)
                dec_decl = dec["decorator_source"]

                if entry_data:
                    entry = entry_data["entry"]
                    # Extract declaration from manifest entry
                    if isinstance(entry, dict):
                        if "weblog_declaration" in entry:
                            import yaml

                            decl_str = yaml.dump(
                                entry["weblog_declaration"], default_flow_style=False, width=70
                            ).strip()
                            entry_decl = f"weblog_declaration:\n{decl_str}"
                        elif "declaration" in entry:
                            decl = entry["declaration"]
                            reason = entry.get("reason", "")
                            if reason:
                                entry_decl = f"{decl} ({reason})"
                            else:
                                entry_decl = decl
                        else:
                            import yaml

                            entry_decl = yaml.dump(entry, default_flow_style=False, width=70).strip()
                    else:
                        entry_decl = str(entry)

                    # Split into lines and align
                    dec_lines = dec_decl.split("\n")
                    entry_lines = entry_decl.split("\n")
                    max_lines = max(len(dec_lines), len(entry_lines))

                    print("REMOVED DECORATOR".ljust(80) + "│" + "MANIFEST ENTRY".ljust(80))
                    print("─" * 80 + "┼" + "─" * 80)

                    for j in range(max_lines):
                        dec_line = dec_lines[j] if j < len(dec_lines) else ""
                        entry_line = entry_lines[j] if j < len(entry_lines) else ""
                        # Pad both to same width for alignment
                        print(dec_line.ljust(80) + "│" + entry_line.ljust(80))
                else:
                    print("REMOVED DECORATOR".ljust(80) + "│" + "MANIFEST ENTRY".ljust(80))
                    print("─" * 80 + "┼" + "─" * 80)
                    dec_lines = dec_decl.split("\n")
                    for dec_line in dec_lines:
                        print(dec_line.ljust(80) + "│" + "(no match)".ljust(80))
                print()

                # Display additional details
                print("ADDITIONAL DETAILS:")
                print("─" * 160)
                print(f"File:     {dec['file']}")
                print(f"Line:     {dec['lineno']}")
                if entry_data:
                    print(f"Component: {entry_data['component']}")
                print()

    # Display unmatched decorators
    if unmatched_decorators:
        print("=" * 160)
        print("UNMATCHED: REMOVED DECORATORS WITHOUT MANIFEST ENTRIES")
        print("=" * 160)

        for idx, unmatched_item in enumerate(unmatched_decorators, 1):
            if len(unmatched_item) == 3:
                nodeid, decs, partial_matches = unmatched_item
            else:
                nodeid, decs = unmatched_item
                partial_matches = []

            print(f"\n{'─' * 160}")
            print(f"UNMATCHED {idx}/{len(unmatched_decorators)}")
            print(f"{'─' * 160}\n")
            print(f"NodeID: {nodeid}\n")

            if partial_matches:
                print(f"⚠️  Found {len(partial_matches)} partial matches (same file, different nodeid):")
                for pm in partial_matches[:3]:  # Show first 3
                    print(f"    - {pm}")
                if len(partial_matches) > 3:
                    print(f"    ... and {len(partial_matches) - 3} more")
                print()

            for dec in decs:
                for line in format_decorator(dec):
                    print(line)
                print()

            print()


if __name__ == "__main__":
    main()
