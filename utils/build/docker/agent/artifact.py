from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import EnvResolver


class Dev(SimpleTarget):
    inputs = (EnvResolver(name="agent_branch", variable_name="AGENT_TARGET_BRANCH", default_value="master-py3"),)
    entries = (text_entry("agent-image", "datadog/agent-dev:{agent_branch.value}"),)


class Prod(Dev):
    pass
