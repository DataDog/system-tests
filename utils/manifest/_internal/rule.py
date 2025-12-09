from utils._context.component_version import Version
from .types import ManifestData, Condition, SkipDeclaration


def match_condition(
    condition: Condition,
    library: str | None = None,
    library_version: Version | None = None,
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
            ref_version = library_version

    if not isinstance(ref_version, Version):
        return False

    if condition["component"] == library or condition["component"] in ("agent", "k8s_cluster_agent", "dd_apm_inject"):
        ret = True

    component_version = condition.get("component_version")
    if component_version:
        ret &= ref_version in component_version

    excluded_component_version = condition.get("excluded_component_version")
    if excluded_component_version:
        ret &= ref_version not in excluded_component_version

    weblog_entry = condition.get("weblog")
    if weblog_entry and weblog:
        ret &= weblog in weblog_entry

    excluded_weblog = condition.get("excluded_weblog")
    if excluded_weblog and weblog:
        ret &= weblog not in excluded_weblog
    return ret


def match_rule(rule: str, nodeid: str) -> bool:
    rule_elements = rule.strip("/").replace("::", "/").split("/")

    nodeid = nodeid[: nodeid.find("[") % len(nodeid) + 1]
    nodeid_elements = nodeid.replace("::", "/").split("/")

    if len(rule_elements) > len(nodeid_elements):
        return False
    return nodeid_elements[: len(rule_elements)] == rule_elements


def get_rules(
    manifest: ManifestData,
    library: str,
    library_version: Version | None = None,
    weblog: str | None = None,
    agent_version: Version | None = None,
    dd_apm_inject_version: Version | None = None,
    k8s_cluster_agent_version: Version | None = None,
) -> dict[str, list[SkipDeclaration]]:
    rules: dict[str, list[SkipDeclaration]] = {}

    for rule, conditions in manifest.items():
        for condition in conditions:
            if not match_condition(
                condition,
                library,
                library_version,
                weblog,
                agent_version,
                dd_apm_inject_version,
                k8s_cluster_agent_version,
            ):
                continue

            if rule not in rules:
                rules[rule] = []
            rules[rule].append(condition["declaration"])

    return rules
