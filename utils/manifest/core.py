from utils.manifest.parser import load
from utils._context.component_version import Version
from utils.manifest.rule import get_rules, match_rule
from utils.manifest.validate import validate_manifest_files as validate

class Manifest:

    def __init__(self,
    library: str,
    library_version: Version | None = None,
    variant: str | None = None,
    agent_version: Version | None = None,
    dd_apm_inject_version: Version | None = None,
    k8s_cluster_agent_version: Version | None = None,
                 path: str= "manifests/"
    ):
        data = load(path)
        self.rules = get_rules(data, library, library_version, variant, agent_version, dd_apm_inject_version, k8s_cluster_agent_version)

    @staticmethod
    def parse(path: str="manifests/"):
        return load()

    @staticmethod
    def validate(path: str = "manifests/"):
        validate(path)

    def get_declarations(self, nodeid: str):
        ret = []
        for rule, declarations in self.rules.items():
            if not match_rule(rule, nodeid):
                continue
            ret += declarations
        return ret
