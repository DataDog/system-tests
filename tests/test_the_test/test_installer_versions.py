import os
from pathlib import Path

import pytest

from utils import scenarios
from utils.scripts import installer_versions


@scenarios.test_the_test
class Test_InstallerVersions:
    def test_custom_library_pins_injector_from_lock(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        lock = tmp_path / "auto_inject.lock"
        lock.write_text("pinned-version\n", encoding="utf-8")
        monkeypatch.setattr(installer_versions, "AUTO_INJECT_LOCK", lock)
        monkeypatch.setenv("DD_INSTALLER_LIBRARY_VERSION", "custom-library")
        monkeypatch.setenv("DD_INSTALLER_INJECTOR_VERSION", "custom-injector")

        installer_versions.set_injector_version_from_lock()

        assert os.environ["DD_INSTALLER_INJECTOR_VERSION"] == "pinned-version"

    def test_default_library_does_not_set_injector(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        lock = tmp_path / "auto_inject.lock"
        lock.write_text("pinned-version\n", encoding="utf-8")
        monkeypatch.setattr(installer_versions, "AUTO_INJECT_LOCK", lock)
        monkeypatch.delenv("DD_INSTALLER_LIBRARY_VERSION", raising=False)
        monkeypatch.delenv("DD_INSTALLER_INJECTOR_VERSION", raising=False)

        installer_versions.set_injector_version_from_lock()

        assert "DD_INSTALLER_INJECTOR_VERSION" not in os.environ

    def test_auto_inject_lock_format(self) -> None:
        contents = installer_versions.AUTO_INJECT_LOCK.read_text(encoding="utf-8")

        assert contents.endswith("\n")
        assert contents.count("\n") == 1
        assert contents.strip() == contents[:-1]
