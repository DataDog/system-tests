import os
import re
import subprocess
from pathlib import Path
from typing import cast

import yaml

from utils import scenarios

INSTALLER_VERSIONS_SCRIPT = Path("utils/build/ssi/base/installer_versions.sh").resolve()
AUTO_INJECT_LOCK = Path("utils/build/auto_inject.lock")
AUTO_INJECT_INSTALLER_PROVISION = Path(
    "utils/build/virtual_machine/provisions/auto-inject/auto-inject_installer_manual.yml"
)


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
        env.pop("SSI_ENV", None)
        env.pop("DD_env", None)

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout == "RESULT=\n"

    def test_prod_without_versions_pins_injector(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env.pop("DD_INSTALLER_LIBRARY_VERSION", None)
        env.pop("DD_INSTALLER_INJECTOR_VERSION", None)
        env.pop("DD_INSTALLER_PINNED_INJECTOR_VERSION", None)
        env["SSI_ENV"] = "prod"
        env.pop("DD_env", None)

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout.splitlines() == [
            "Using pinned injector version from auto_inject.lock: pinned-version",
            "RESULT=pinned-version",
        ]

    def test_prod_dd_env_without_versions_pins_injector(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env.pop("DD_INSTALLER_LIBRARY_VERSION", None)
        env.pop("DD_INSTALLER_INJECTOR_VERSION", None)
        env.pop("DD_INSTALLER_PINNED_INJECTOR_VERSION", None)
        env.pop("SSI_ENV", None)
        env["DD_env"] = "prod"

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout.splitlines() == [
            "Using pinned injector version from auto_inject.lock: pinned-version",
            "RESULT=pinned-version",
        ]

    def test_dev_without_versions_does_not_set_injector(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env.pop("DD_INSTALLER_LIBRARY_VERSION", None)
        env.pop("DD_INSTALLER_INJECTOR_VERSION", None)
        env["SSI_ENV"] = "dev"
        env.pop("DD_env", None)

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout == "RESULT=\n"

    def test_prod_explicit_injector_is_not_overridden(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env.pop("DD_INSTALLER_LIBRARY_VERSION", None)
        env["DD_INSTALLER_INJECTOR_VERSION"] = "custom-injector"
        env["SSI_ENV"] = "prod"
        env.pop("DD_env", None)

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout == "RESULT=custom-injector\n"

    def test_dev_custom_library_still_pins_injector(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env["DD_INSTALLER_LIBRARY_VERSION"] = "custom-library"
        env.pop("DD_INSTALLER_INJECTOR_VERSION", None)
        env.pop("DD_INSTALLER_PINNED_INJECTOR_VERSION", None)
        env["SSI_ENV"] = "dev"
        env.pop("DD_env", None)

        result = _run_installer_versions_script(tmp_path, env)

        assert result.stdout.splitlines() == [
            "Using pinned injector version from auto_inject.lock: pinned-version",
            "RESULT=pinned-version",
        ]

    def test_missing_lock_file_fails_loud(self, tmp_path: Path) -> None:
        env = os.environ.copy()
        env["DD_INSTALLER_LIBRARY_VERSION"] = "custom-library"
        env.pop("DD_INSTALLER_INJECTOR_VERSION", None)
        env.pop("DD_INSTALLER_PINNED_INJECTOR_VERSION", None)

        result = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1"; printf "RESULT=%s\\n" "${DD_INSTALLER_INJECTOR_VERSION:-}"',
                "bash",
                str(INSTALLER_VERSIONS_SCRIPT),
            ],
            cwd=tmp_path,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "auto_inject.lock" in result.stderr
        assert "RESULT=" not in result.stdout

    def test_auto_inject_lock_format(self) -> None:
        contents = AUTO_INJECT_LOCK.read_text(encoding="utf-8")

        assert contents.endswith("\n")
        assert contents.count("\n") == 1
        assert contents.strip() == contents[:-1]
        # Injector OCI tags carry a package revision; a bare x.y.z tag does not exist in the registry.
        assert re.fullmatch(r"\d+\.\d+\.\d+-\d+", contents.strip())

    def test_windows_installer_pins_injector_from_lock(self) -> None:
        provisions = cast(
            "list[dict[str, object]]", yaml.safe_load(AUTO_INJECT_INSTALLER_PROVISION.read_text(encoding="utf-8"))
        )
        windows_provision = next(provision for provision in provisions if provision.get("os_type") == "windows")
        copied_files = cast("list[dict[str, str]]", windows_provision["copy_files"])
        remote_command = cast("str", windows_provision["remote-command"])

        assert any(file["local_path"] == "utils/build/auto_inject.lock" for file in copied_files)
        assert (
            '-not $env:DD_INSTALLER_INJECTOR_VERSION -and ($env:DD_INSTALLER_LIBRARY_VERSION -or $env:DD_env -eq "prod")'
            in remote_command
        )
        assert "[System.IO.File]::ReadAllText($AUTO_INJECT_LOCK_PATH).Trim()" in remote_command
        assert (
            "$env:DD_INSTALLER_DEFAULT_PKG_VERSION_DATADOG_APM_INJECT = $env:DD_INSTALLER_INJECTOR_VERSION"
            in remote_command
        )
