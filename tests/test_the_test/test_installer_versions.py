import os
import subprocess
from pathlib import Path

from utils import scenarios

INSTALLER_VERSIONS_SCRIPT = Path("utils/build/ssi/base/installer_versions.sh").resolve()
AUTO_INJECT_LOCK = Path("auto_inject.lock")


def _run_installer_versions_script(tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    (tmp_path / "auto_inject.lock").write_text("pinned-version\n", encoding="utf-8")
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; printf "RESULT=%s\\n" "${DD_INSTALLER_INJECTOR_VERSION:-}"',
            "bash",
            str(INSTALLER_VERSIONS_SCRIPT),
        ],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@scenarios.test_the_test
class Test_InstallerVersions:
    def test_custom_library_pins_injector_from_lock(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env["DD_INSTALLER_LIBRARY_VERSION"] = "custom-library"
        env.pop("DD_INSTALLER_INJECTOR_VERSION", None)

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout.splitlines() == [
            "Using pinned injector version from auto_inject.lock: pinned-version",
            "RESULT=pinned-version",
        ]

    def test_custom_injector_is_not_overridden(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env["DD_INSTALLER_LIBRARY_VERSION"] = "custom-library"
        env["DD_INSTALLER_INJECTOR_VERSION"] = "custom-injector"

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout == "RESULT=custom-injector\n"

    def test_docker_build_argument_supplies_pinned_injector(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env["DD_INSTALLER_LIBRARY_VERSION"] = "custom-library"
        env["DD_INSTALLER_PINNED_INJECTOR_VERSION"] = "docker-pinned-version"
        env.pop("DD_INSTALLER_INJECTOR_VERSION", None)

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout.splitlines() == [
            "Using pinned injector version from auto_inject.lock: docker-pinned-version",
            "RESULT=docker-pinned-version",
        ]

    def test_default_library_does_not_set_injector(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env.pop("DD_INSTALLER_LIBRARY_VERSION", None)
        env.pop("DD_INSTALLER_INJECTOR_VERSION", None)

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout == "RESULT=\n"

    def test_auto_inject_lock_format(self) -> None:
        contents = AUTO_INJECT_LOCK.read_text(encoding="utf-8")

        assert contents.endswith("\n")
        assert contents.count("\n") == 1
        assert contents.strip() == contents[:-1]
