from __future__ import annotations

import os
from pathlib import Path
import subprocess

from utils import scenarios


SCRIPT = Path("utils/scripts/load-binary.sh")
C_LIBRARY_PROD_IMAGE = "install.datadoghq.com/apm-library-c-package:latest"
C_INJECTOR_PROD_IMAGE = "install.datadoghq.com/apm-inject-package:latest"
C_LIBRARY_SHA = "1" * 40
C_INJECTOR_SHA = "2" * 40


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)


def _run_loader(
    tmp_path: Path,
    version: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    binaries_dir = tmp_path / "binaries"
    bin_dir.mkdir()
    binaries_dir.mkdir()

    _write_executable(
        bin_dir / "curl",
        f"""#!/usr/bin/env bash
set -eu
url="${{!#}}"
printf '%s\\n' "$url" >> "$CURL_CALLS"
if [[ "${{MISSING_BRANCH:-}}" != "" && "$url" == *"${{MISSING_BRANCH}}"* ]]; then
    exit 22
fi
if [[ "$url" == *"DataDog/dd-trace-c"* ]]; then
    printf '%s\\n' '{{"commit":{{"sha":"{C_LIBRARY_SHA}"}}}}'
else
    printf '%s\\n' '{{"commit":{{"sha":"{C_INJECTOR_SHA}"}}}}'
fi
""",
    )
    _write_executable(
        bin_dir / "docker",
        """#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$DOCKER_CALLS"
if [[ "${FAIL_IMAGE:-}" != "" && "$*" == *"$FAIL_IMAGE"* ]]; then
    exit 1
fi
""",
    )

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "BINARIES_DIR": str(binaries_dir),
        "CURL_CALLS": str(tmp_path / "curl-calls"),
        "DOCKER_CALLS": str(tmp_path / "docker-calls"),
    }
    env.pop("LIBRARY_TARGET_BRANCH", None)
    env.pop("AUTO_INJECT_TARGET_BRANCH", None)
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(SCRIPT), "c", version],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@scenarios.test_the_test
class Test_LoadBinaryC:
    def test_native_library_is_loaded_by_auto_inject(self) -> None:
        dockerfile = Path("utils/build/docker/c/python-stdlib.Dockerfile").read_text(encoding="utf-8")
        launcher = Path("utils/build/docker/c/python-stdlib/app.sh").read_text(encoding="utf-8")

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
        assert C_LIBRARY_PROD_IMAGE in docker_calls
        assert C_INJECTOR_PROD_IMAGE in docker_calls

    def test_independent_branch_overrides_resolve_to_sha_tags(self, tmp_path: Path) -> None:
        result = _run_loader(
            tmp_path,
            "dev",
            extra_env={
                "LIBRARY_TARGET_BRANCH": "feature/c-client",
                "AUTO_INJECT_TARGET_BRANCH": "feature/injector",
            },
        )

        assert result.returncode == 0, result.stderr
        curl_calls = (tmp_path / "curl-calls").read_text(encoding="utf-8")
        assert "feature%2Fc-client" in curl_calls
        assert "feature%2Finjector" in curl_calls
        assert (tmp_path / "binaries/c-library-image").read_text(encoding="utf-8").strip() == (
            f"installtesting.datad0g.com/apm-library-c-package:{C_LIBRARY_SHA}"
        )
        assert (tmp_path / "binaries/c-injector-image").read_text(encoding="utf-8").strip() == (
            f"installtesting.datad0g.com/apm-inject-package:{C_INJECTOR_SHA}"
        )

    def test_missing_branch_fails_before_package_validation(self, tmp_path: Path) -> None:
        result = _run_loader(
            tmp_path,
            "dev",
            extra_env={"LIBRARY_TARGET_BRANCH": "missing", "MISSING_BRANCH": "missing"},
        )

        assert result.returncode != 0
        assert "Unable to resolve branch 'missing' in DataDog/dd-trace-c" in result.stderr
        assert not (tmp_path / "docker-calls").exists()

    def test_missing_package_fails_with_clear_error(self, tmp_path: Path) -> None:
        result = _run_loader(
            tmp_path,
            "dev",
            extra_env={"FAIL_IMAGE": "apm-inject-package"},
        )

        assert result.returncode != 0
        assert "OCI package does not exist or is not accessible" in result.stderr
