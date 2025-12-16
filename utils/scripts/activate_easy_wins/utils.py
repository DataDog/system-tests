from __future__ import annotations
import ast
from pathlib import Path


CLASS_LENGTH = 2
FUNCTION_LENGTH = 3


def get_impacted_nodeids(rule: str) -> set[str]:
    elements = rule.split("::")
    if len(elements) == FUNCTION_LENGTH:
        return {rule}

    path = Path(elements[0])
    ret = set()

    if path.is_dir():
        if len(elements) >= CLASS_LENGTH:
            raise ValueError(f"When a class is specified the path should be a file, {path} is a dir")
        for child in path.iterdir():
            if "__pycache__" in child.name:
                continue
            ret |= get_impacted_nodeids(str(child))
        return ret

    if path.suffix != ".py":
        return set()
    with path.open() as f:
        test_ast = ast.parse(f.read())

    if len(elements) == CLASS_LENGTH:
        for node in ast.iter_child_nodes(test_ast):
            if not isinstance(node, ast.ClassDef) or node.name != elements[1]:
                continue
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.FunctionDef):
                    ret.add(f"{path}::{elements[1]}::{child.name}")
        return ret

    for node in ast.iter_child_nodes(test_ast):
        if not isinstance(node, ast.ClassDef):
            continue
        ret |= get_impacted_nodeids(f"{path}::{node.name}")

    return ret
