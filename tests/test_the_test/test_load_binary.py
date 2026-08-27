from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from utils import scenarios
from utils.target_artifacts.orchestrator import MANIFEST_FILENAME


SCRIPT = Path("utils/scripts/load-binary.sh")
C_LIBRARY_DIGEST = "sha256:" + ("a" * 64)
C_INJECTOR_DIGEST = "sha256:" + ("b" * 64)
C_LIBRARY_PROD_IMAGE = f"install.datadoghq.com/apm-library-c-package@{C_LIBRARY_DIGEST}"
C_INJECTOR_PROD_IMAGE = f"install.datadoghq.com/apm-inject-package@{C_INJECTOR_DIGEST}"
C_LIBRARY_SHA = "1" * 40
C_INJECTOR_SHA = "2" * 40


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)


def _run_loader(
    tmp_path: Path,
    version: str,
    *,
    target: str = "c",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    binaries_dir = tmp_path / "binaries"
    bin_dir.mkdir()
    binaries_dir.mkdir()

    _write_executable(
        bin_dir / "docker",
        f"""#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$DOCKER_CALLS"
if [[ "${{FAIL_IMAGE:-}}" != "" && "$*" == *"$FAIL_IMAGE"* ]]; then
    exit 1
fi
if [[ "$*" == *"apm-library-c-package"* ]]; then
    printf 'Name: apm-library-c-package\\nDigest: {C_LIBRARY_DIGEST}\\n'
else
    printf 'Name: apm-inject-package\\nDigest: {C_INJECTOR_DIGEST}\\n'
fi
""",
    )
    _write_executable(
        bin_dir / "curl",
        """#!/usr/bin/env bash
set -eu
output=""
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--output" ]; then
        shift
        output="$1"
    fi
    shift
done
printf '{"rules":[]}\\n' > "$output"
""",
    )

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "BINARIES_DIR": str(binaries_dir),
        "DOCKER_CALLS": str(tmp_path / "docker-calls"),
    }
    env.pop("LIBRARY_TARGET_BRANCH", None)
    env.pop("AUTO_INJECT_TARGET_BRANCH", None)
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(SCRIPT), target, version],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@scenarios.test_the_test
class Test_LoadBinaryC:
    def test_stage_target_artifacts_entrypoint_imports_without_pythonpath(self) -> None:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)

        result = subprocess.run(
            ["python3", "utils/scripts/stage-target-artifacts.py", "--help"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        assert "usage: stage-target-artifacts" in result.stdout

    def test_native_library_is_loaded_by_auto_inject(self) -> None:
        dockerfile = Path("utils/build/docker/c/perl-mojolicious.Dockerfile").read_text(encoding="utf-8")
        launcher = Path("utils/build/docker/c/perl-mojolicious/app.sh").read_text(encoding="utf-8")

        assert "DD_INJECT_NATIVE=always" in dockerfile
        assert "DD_TRACE_HOOK_MODULES=socket" in dockerfile
        assert "libdd_autoinstrument.so" not in launcher
        assert 'export LD_PRELOAD="${launcher}${LD_PRELOAD:+:${LD_PRELOAD}}"' in launcher

    def test_production_package_defaults(self, tmp_path: Path) -> None:
        result = _run_loader(tmp_path, "prod")

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "binaries/c-library-image").read_text(encoding="utf-8").strip() == C_LIBRARY_PROD_IMAGE
        assert (tmp_path / "binaries/c-injector-image").read_text(encoding="utf-8").strip() == C_INJECTOR_PROD_IMAGE
        docker_calls = (tmp_path / "docker-calls").read_text(encoding="utf-8")
        assert "install.datadoghq.com/apm-library-c-package:latest" in docker_calls
        assert "install.datadoghq.com/apm-inject-package:latest" in docker_calls

    def test_development_package_defaults_to_production_without_overrides(self, tmp_path: Path) -> None:
        result = _run_loader(tmp_path, "dev")

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "binaries/c-library-image").read_text(encoding="utf-8").strip() == C_LIBRARY_PROD_IMAGE
        assert (tmp_path / "binaries/c-injector-image").read_text(encoding="utf-8").strip() == C_INJECTOR_PROD_IMAGE
        docker_calls = (tmp_path / "docker-calls").read_text(encoding="utf-8")
        assert "install.datadoghq.com/apm-library-c-package:latest" in docker_calls
        assert "install.datadoghq.com/apm-inject-package:latest" in docker_calls

    def test_single_branch_override_keeps_other_component_on_production(self, tmp_path: Path) -> None:
        result = _run_loader(tmp_path, "dev", extra_env={"LIBRARY_TARGET_BRANCH": C_LIBRARY_SHA})

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "binaries/c-library-image").read_text(encoding="utf-8").strip() == (
            f"installtesting.datad0g.com/apm-library-c-package:{C_LIBRARY_SHA}"
        )
        assert (tmp_path / "binaries/c-injector-image").read_text(encoding="utf-8").strip() == C_INJECTOR_PROD_IMAGE

    def test_independent_branch_overrides_resolve_to_sha_tags(self, tmp_path: Path) -> None:
        result = _run_loader(
            tmp_path,
            "dev",
            extra_env={
                "LIBRARY_TARGET_BRANCH": C_LIBRARY_SHA,
                "AUTO_INJECT_TARGET_BRANCH": C_INJECTOR_SHA,
            },
        )

        assert result.returncode == 0, result.stderr
        assert not (tmp_path / "docker-calls").exists()
        assert (tmp_path / "binaries/c-library-image").read_text(encoding="utf-8").strip() == (
            f"installtesting.datad0g.com/apm-library-c-package:{C_LIBRARY_SHA}"
        )
        assert (tmp_path / "binaries/c-injector-image").read_text(encoding="utf-8").strip() == (
            f"installtesting.datad0g.com/apm-inject-package:{C_INJECTOR_SHA}"
        )

    def test_production_rejects_branch_overrides_before_package_validation(self, tmp_path: Path) -> None:
        result = _run_loader(
            tmp_path,
            "prod",
            extra_env={"LIBRARY_TARGET_BRANCH": C_LIBRARY_SHA},
        )

        assert result.returncode != 0
        assert "Target branches can only be used with the development c packages" in result.stderr
        assert not (tmp_path / "docker-calls").exists()

    def test_missing_package_fails_with_clear_error(self, tmp_path: Path) -> None:
        result = _run_loader(
            tmp_path,
            "dev",
            extra_env={"FAIL_IMAGE": "apm-inject-package"},
        )

        assert result.returncode != 0
        assert "Unable to resolve OCI digest" in result.stderr

    def test_agent_dependency_uses_target_artifact_staging(self, tmp_path: Path) -> None:
        result = _run_loader(
            tmp_path,
            "dev",
            target="agent",
            extra_env={"AGENT_TARGET_BRANCH": "feature-agent"},
        )

        assert result.returncode == 0, result.stderr
        binaries_dir = tmp_path / "binaries"
        assert (binaries_dir / "agent-image").read_text(encoding="utf-8").strip() == ("datadog/agent-dev:feature-agent")
        manifest = json.loads((binaries_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        assert manifest["entries"]["agent-image"]["owner"] == {
            "target": "agent",
            "environment": "dev",
        }

    def test_waf_rule_set_overlay_stays_outside_target_manifest(self, tmp_path: Path) -> None:
        result = _run_loader(tmp_path, "dev", target="waf_rule_set")

        assert result.returncode == 0, result.stderr
        binaries_dir = tmp_path / "binaries"
        assert json.loads((binaries_dir / "waf_rule_set.json").read_text(encoding="utf-8")) == {"rules": []}
        assert not (binaries_dir / MANIFEST_FILENAME).exists()
