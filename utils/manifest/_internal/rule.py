from utils._context.component_version import NoneVersion, Version
from .types import ManifestData, Condition, SkipDeclaration


def match_condition(
    condition: Condition,
    components: dict[str, Version],
    weblog: str | None = None,
) -> bool:
    component = condition["component"]

    if component not in components:
        return False
    ret = True
    component_tested_version = components[component]

    assert isinstance(component_tested_version, Version), (
        f"Version not found for {condition['component']}, got {component_tested_version}"
    )

    assert not isinstance(component_tested_version, NoneVersion), (
        f"Version of tested component {component} should be initialized"
    )

    component_version = condition.get("component_version")
    if component_version:
        ret &= component_tested_version in component_version

    excluded_component_version = condition.get("excluded_component_version")
    if excluded_component_version:
        ret &= component_tested_version not in excluded_component_version

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
    components: dict[str, Version],
    weblog: str | None = None,
) -> dict[str, list[SkipDeclaration]]:
    rules: dict[str, list[SkipDeclaration]] = {}

    for rule, conditions in manifest.items():
        for condition in conditions:
            if not match_condition(
                condition,
                components,
                weblog,
            ):
                continue

            if rule not in rules:
                rules[rule] = []
            rules[rule].append(condition["declaration"])

    return rules
