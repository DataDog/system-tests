from typing import Any

from utils._context.component_version import Version
from utils._decorators import _TestDeclaration, parse_skip_declaration


def match_condition(
    condition: dict[str, Any],
    component: str | None = None,
    component_version: Version | None = None,
    weblog: str | None = None,
    agent_version: Version | None = None,
    dd_apm_inject_version: Version | None = None,
    k8s_cluster_agent_version: Version | None = None,
) -> bool:
    ret = False

    match condition["component"]:
        case "agent":
            ref_version = agent_version
        case "k8s_cluster_agent":
            ref_version = k8s_cluster_agent_version
        case "dd_apm_inject":
            ref_version = dd_apm_inject_version
        case _:
            ref_version = component_version

    if not ref_version:
        return True

    if condition["component"] == component or component in ("agent", "k8s_cluster_agent", "dd_apm_inject"):
        ret = True
    if condition.get("component_version"):
        ret &= ref_version in condition["component_version"]
    if condition.get("excluded_component_version"):
        ret &= ref_version not in condition["excluded_component_version"]
    if condition.get("weblog"):
        if isinstance(condition["weblog"], list):
            ret &= weblog in condition["weblog"]
        else:
            ret &= weblog == condition["weblog"]
    if condition.get("excluded_weblog"):
        if isinstance(condition["excluded_weblog"], list):
            ret &= weblog not in condition["excluded_weblog"]
        else:
            ret &= weblog != condition["excluded_weblog"]
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
    manifest: dict[str, list[dict[str, Any]]],
    component: str,
    component_version: Version | None = None,
    weblog: str | None = None,
    agent_version: Version | None = None,
    dd_apm_inject_version: Version | None = None,
    k8s_cluster_agent_version: Version | None = None,
) -> dict[str, list[tuple[_TestDeclaration, str | None]]]:
    rules: dict[str, list[tuple[_TestDeclaration, str | None]]] = {}

    for rule, conditions in manifest.items():
        for condition in conditions:
            if not match_condition(
                condition,
                component,
                component_version,
                weblog,
                agent_version,
                dd_apm_inject_version,
                k8s_cluster_agent_version,
            ):
                continue

            if rule not in rules:
                rules[rule] = []
            rules[rule].append((condition["declaration"].value, condition["declaration"].reason))

    return rules
