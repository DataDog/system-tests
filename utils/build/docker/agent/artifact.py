from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import ArtifactEntry, LiteralValue
from utils.target_artifacts.resolvers import EnvResolver


class Dev:
    def artifact_inputs(self, env: dict[str, str]) -> tuple[EnvResolver]:
        return (EnvResolver(name="agent_branch", variable_name="AGENT_TARGET_BRANCH", default_value="master-py3"),)

    def artifact_entries(
        self,
        resolved_inputs: dict[str, LiteralValue],
    ) -> tuple[ArtifactEntry]:
        return (text_entry("agent-image", f"datadog/agent-dev:{resolved_inputs['agent_branch'].value}"),)


class Prod(Dev):
    pass
