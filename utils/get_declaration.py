from typing import Any

from utils._context.component_version import Version
from utils._decorators import _TestDeclaration, parse_skip_declaration


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
            ref_version = agent_version
        case "k8s_cluster_agent":
            ref_version = k8s_cluster_agent_version
        case "dd_apm_inject":
            ref_version = dd_apm_inject_version
        case _:
            ref_version = library_version

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
