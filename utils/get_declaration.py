import semantic_version as semver
from manifests.parser.core import load as load_manifests
from utils._decorators import parse_skip_declaration

def match_condition(condition, library=None, library_version=None, variant=None, agent_version=None, dd_apm_inject_version=None, k8s_cluster_agent_version=None):
    ret = False
    ref_version = library_version
    match condition["library"]:
        case "agent":
            ref_version = agent_version
        case "k8s_cluster_agent":
            ref_version = k8s_cluster_agent_version
        case "dd_apm_inject":
            ref_version = dd_apm_inject_version
        case _:
            ref_version = library_version

    if isinstance(ref_version, str):
        return False
    ref_version = semver.Version(str(ref_version))

    if condition["library"] == library or library in ("agent", "k8s_cluster_agent", "dd_apm_inject"):
        ret = True
    if condition.get("library_version"):
        ret &= ref_version in condition["library_version"]
    if condition.get("variant"):
        ret &= variant in condition["variant"]
    if condition.get("excluded_variant"):
        ret &= variant not in condition["excluded_variant"]
    return ret


def get_declarations(library: str, library_version=None, variant=None, agent_version=None, dd_apm_inject_version=None, k8s_cluster_agent_version=None, manifests_path = "manifests/"):
    declarations = {}

    rules = load_manifests()
    for rule, conditions in rules.items():
        for condition in conditions:
            if match_condition(condition, library, library_version, variant, agent_version, dd_apm_inject_version, k8s_cluster_agent_version):
                if rule not in declarations:
                    declarations[rule] = []
                declarations[rule].append(parse_skip_declaration(condition["declaration"]))
                declarations[rule][-1][1] = f"{library}: {declarations[rule][-1][1]}"

    return declarations




