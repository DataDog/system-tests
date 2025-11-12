from typing import Any
from pathlib import Path

from utils._context.component_version import Version
from utils._decorators import _TestDeclaration, parse_skip_declaration

import ast
from typing import List, Union

def class_methods_in_file(path: Path, start: str|None = None) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    try:
        tree = ast.parse(source, filename=path, type_comments=True)
    except SyntaxError as e:
        raise SyntaxError(f"Failed to parse {path}: {e}") from e

    results: List[str] = []

    def visit_class(node: ast.ClassDef, qual: str) -> None:
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test"):
                results.append(f"{qual}::{child.name}")
            elif isinstance(child, ast.ClassDef):
                visit_class(child, f"{qual}::{child.name}")

    for n in tree.body:
        if isinstance(n, ast.ClassDef) and (not start or n.name == start):
            visit_class(n, n.name)

    return results

def update_condition(condition, contexts):
    def process_only_declaration(name, condition, contexts):
        if len(condition) == 2:
            if len(contexts) == 1:
                condition["excluded_variant"] = next(iter(contexts)).variant
                return False
            condition["excluded_variant"] = []
            for context in contexts:
                condition["excluded_variant"].append(context.variant)
            return False
        return True

    def process_variant(name, condition, contexts):
        for context in contexts:
            if isinstance(condition[name], str) and context.variant == condition[name]:
                condition[name] = []
            elif context.variant in condition[name]:
                condition[name].remove(context.variant)
        if len(condition[name]) == 0:
            condition["remove"] = True
        return len(condition) > 2

    def process_excluded_variant(name, condition, contexts):
        for context in contexts:
            if isinstance(condition[name], str) and context.variant != condition[name]:
                condition[name] = [condition[name], context.variant]
            elif context.variant not in condition[name]:
                condition[name].append(context.variant)
        return len(condition) > 2

    clause_processors = [
            ("declaration", process_only_declaration),
            ("variant", process_variant),
            ("excluded_variant", process_excluded_variant)
            ]

    create_new_rule = False
    for name, clause_processor in clause_processors:
        if name in condition:
            create_new_rule |= clause_processor(name, condition, contexts)

def update_rule(rule, contexts, raw):
    for icondition, condition in enumerate(rule):
        matched_condition = False
        for context in contexts:
            if match_condition(condition, context.library, context.library_version, context.variant):
                matched_condition = True
        if matched_condition:
            update_condition(condition, contexts)
        else:
            rule[icondition] = raw[icondition]

    len_rule = len(rule)
    for icondition, condition in enumerate(rule[::-1]):
        if condition.get("remove"):
            del rule[len_rule - icondition - 1]


def is_terminal(rule):
    return len(rule.split("::")) >= 3

def get_all_nodeids(rule):
    path = Path(rule[:rule.find("::")%(len(rule)+1)])
    obj = rule[rule.find("::")%(len(rule)+1)+2:]

    if is_terminal(rule):
        return [rule]

    paths = list(path.glob("**/test*.py"))
    if path.is_file():
        paths.append(path)
    nodeids = []
    for file in paths:
        for function_id in class_methods_in_file(file):
            nodeids.append(f"{file}::{function_id}")

    return nodeids


def match_condition(
    condition: dict[str, Any],
    library: str | None = None,
    library_version: Version | None = None,
    variant: str | None = None,
    agent_version: Version | None = None,
    dd_apm_inject_version: Version | None = None,
    k8s_cluster_agent_version: Version | None = None,
) -> bool:
    ret = False

    match condition["library"]:
        case "agent":
            ref_version = agent_version or library_version
        case "k8s_cluster_agent":
            ref_version = k8s_cluster_agent_version or library_version
        case "dd_apm_inject":
            ref_version = dd_apm_inject_version or library_version
        case _:
            ref_version = library_version or library_version

    if not ref_version:
        return True

    if condition["library"] == library or library in ("agent", "k8s_cluster_agent", "dd_apm_inject"):
        ret = True
    if condition.get("library_version"):
        ret &= ref_version in condition["library_version"]
    if condition.get("variant"):
        if isinstance(condition["variant"], list):
            ret &= variant in condition["variant"]
        else:
            ret &= variant == condition["variant"]
    if condition.get("excluded_variant"):
        if isinstance(condition["excluded_variant"], list):
            ret &= variant not in condition["excluded_variant"]
        else:
            ret &= variant != condition["excluded_variant"]
    return ret


def match_rule(rule: str, nodeid: str) -> bool:
    path = rule.split("/")
    path = [part for part in path if part]
    rest = rule.split("::")
    rule_elements = path[:-1] + [path[-1].split("::")[0]] + rest[1:]

    nodeid = nodeid[: nodeid.find("[") % len(nodeid) + 1]
    path = nodeid.split("/")
    rest = nodeid.split("::")
    nodeid_elements = path[:-1] + [path[-1].split("::")[0]] + rest[1:]

    if len(rule_elements) > len(nodeid_elements):
        return False
    return all(elements[0] == elements[1] for elements in zip(rule_elements, nodeid_elements, strict=False))


def get_rules(
    library: str,
    library_version: Version | None = None,
    variant: str | None = None,
    agent_version: Version | None = None,
    dd_apm_inject_version: Version | None = None,
    k8s_cluster_agent_version: Version | None = None,
) -> dict[str, list[tuple[_TestDeclaration, str | None]]]:
    from manifests.parser.core import load as load_manifests

    rules: dict[str, list[tuple[_TestDeclaration, str | None]]] = {}

    manifests = load_manifests()
    for rule, conditions in manifests.items():
        for condition in conditions:
            if not match_condition(
                condition,
                library,
                library_version,
                variant,
                agent_version,
                dd_apm_inject_version,
                k8s_cluster_agent_version,
            ):
                continue

            if rule not in rules:
                rules[rule] = []
            declaration_tuple = parse_skip_declaration(condition["declaration"])
            rules[rule].append(declaration_tuple)

    return rules
