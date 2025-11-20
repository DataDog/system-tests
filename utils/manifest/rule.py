from utils._context.component_version import Version
from utils._decorators import _TestDeclaration
from utils.manifest.types import ManifestData, Condition


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

    if not ref_version:
        return True

    if condition["component"] == library or condition["component"] in ("agent", "k8s_cluster_agent", "dd_apm_inject"):
        ret = True
    if condition.get("component_version"):
        assert condition["component_version"]  # To reassure mypy
        ret &= ref_version in condition["component_version"]
    if condition.get("excluded_component_version"):
        assert condition["excluded_component_version"]  # To reassure mypy
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
    manifest: ManifestData,
    library: str,
    library_version: Version | None = None,
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
            rules[rule].append((condition["declaration"].declaration, condition["declaration"].details))

    return rules
