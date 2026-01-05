from utils._context.component_version import Version
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
    tested_component_version = components[component]

    assert isinstance(tested_component_version, Version), (
        f"Version not found for {condition['component']},\
        got {tested_component_version} (type {type(tested_component_version)})"
    )

    component_version = condition.get("component_version")
    if component_version:
        ret &= tested_component_version in component_version

    excluded_component_version = condition.get("excluded_component_version")
    if excluded_component_version:
        ret &= tested_component_version not in excluded_component_version

    weblog_entry = condition.get("weblog")
    if weblog_entry and weblog:
        ret &= weblog in weblog_entry

    excluded_weblog = condition.get("excluded_weblog")
    if excluded_weblog and weblog:
        ret &= weblog not in excluded_weblog
    return ret


def match_rule(rule: str, nodeid: str) -> bool:
    rule_elements = rule.strip("/").replace("::", "/").split("/")

    nodeid_elements = nodeid.replace("::", "/").split("/")

    if len(rule_elements) > len(nodeid_elements):
        return False
    return nodeid_elements[: len(rule_elements)] == rule_elements


def get_rules(
    manifest: ManifestData,
    components: dict[str, Version],
    weblog: str | None = None,
) -> tuple[dict[str, list[SkipDeclaration]], dict[str, list[tuple[int, int]]]]:
    rules: dict[str, list[SkipDeclaration]] = {}
    tracker: dict[str, list[tuple[int, int]]] = {}

    for rule, conditions in manifest.items():
        in_component_index = -1
        for condition_index, condition in enumerate(conditions):
            if condition["component"] in components:
                in_component_index += 1
            if not match_condition(
                condition,
                components,
                weblog,
            ):
                continue

            if rule not in rules:
                rules[rule] = []
            rules[rule].append(condition["declaration"])
            if rule not in tracker:
                tracker[rule] = []
            tracker[rule].append((condition_index, in_component_index))

    return rules, tracker
