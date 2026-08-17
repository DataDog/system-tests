from __future__ import annotations

import os
from pathlib import Path

from .entry_helpers import text_entry
from .models import TargetArtifactError
from .orchestrator import write_artifact_entries


def stage_legacy_dependency(
    target: str,
    environment: str,
    *,
    repo_root: Path | None = None,
    binaries_dir: Path | None = None,
    process_env: dict[str, str] | None = None,
) -> bool:
    if target != "agent":
        return False
    if environment != "dev":
        raise TargetArtifactError(f"Don't know how to load version {environment} for {target}")

    env = dict(os.environ if process_env is None else process_env)
    output_dir = Path(env.get("BINARIES_DIR", "binaries")) if binaries_dir is None else binaries_dir
    if not output_dir.is_absolute():
        output_dir = (Path.cwd() if repo_root is None else repo_root) / output_dir

    branch = env.get("AGENT_TARGET_BRANCH", "master-py3")
    write_artifact_entries(
        output_dir,
        target,
        "dependency",
        (text_entry("agent-image", f"datadog/agent-dev:{branch}"),),
    )
    return True
