from __future__ import annotations
import ast
from pathlib import Path


CLASS_LENGTH = 2
FUNCTION_LENGTH = 3


class Dir:
    pass


class File:
    def __init__(self, file_path: Path):
        self.classes = None
        with file_path.open() as f:
            self.ast = ast.parse(f.read())

    def get_classes(self) -> list[Class]:
        if self.classes is not None:
            return self.classes
        self.classes = []
        for node in ast.iter_child_nodes(self.ast):
            if isinstance(node, ast.ClassDef):
                self.classes.append(Class(node, self))
        return self.classes


class Class:
    def __init__(self, node: ast.ClassDef, parent: File):
        self.node = node
        self.parent = parent
        self.functions = None

    def get_functions(self) -> list[ast.FunctionDef]:
        if self.functions is not None:
            return self.functions
        self.functions = []
        for node in ast.iter_child_nodes(self.node):
            if isinstance(node, ast.FunctionDef):
                self.functions.append(Function(node, self))
        return self.functions


class Function:
    def __init__(self, node: ast.FunctionDef, parent: Class):
        self.node = node
        self.parent = parent

    def __str__(self) -> str:
        return ""


def get_impacted_nodeids(rule: str) -> list[str]:
    elements = rule.split("::")

    if len(elements) == FUNCTION_LENGTH:
        return [rule]
    if len(elements) == CLASS_LENGTH:
        file = elements[0]
    else:
        dirs = elements[0]

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
    return [""]
