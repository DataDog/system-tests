from pathlib import Path

import pytest

from utils.scripts.update_agent_version import (
    DOCKER_COMPOSE_PROVISION,
    INSTALLER_PROVISION,
    normalize_version,
    update_agent_version,
)


def write_pins(root: Path) -> None:
    installer = root / INSTALLER_PROVISION
    installer.parent.mkdir(parents=True)
    installer.write_text(
        "remote-command: |\n"
        "    # Pin to 7.78.4 agent release. APMSP-3059\n"
        "    export DD_AGENT_MAJOR_VERSION=7\n"
        "    export DD_AGENT_MINOR_VERSION=78.4\n"
        "    echo install\n"
    )
    compose = root / DOCKER_COMPOSE_PROVISION
    compose.parent.mkdir(parents=True)
    compose.write_text(
        "services:\n"
        "  datadog:\n"
        "    # Pin to 7.78.4 agent release. APMSP-3059\n"
        "    image: gcr.io/datadoghq/agent:7.78.4\n"
    )


def test_update_agent_version_updates_both_ssi_pins(tmp_path: Path) -> None:
    write_pins(tmp_path)

    assert update_agent_version(tmp_path, "v7.82.3")
    assert "DD_AGENT_MINOR_VERSION=82.3" in (tmp_path / INSTALLER_PROVISION).read_text()
    assert "gcr.io/datadoghq/agent:7.82.3" in (tmp_path / DOCKER_COMPOSE_PROVISION).read_text()
    assert "updated automatically by APMSP-3752" in (tmp_path / INSTALLER_PROVISION).read_text()

    assert not update_agent_version(tmp_path, "7.82.3")


@pytest.mark.parametrize("version", ["8.0.0", "7.82", "7.82.3-rc.1", "latest"])
def test_normalize_version_rejects_unsupported_versions(version: str) -> None:
    with pytest.raises(ValueError, match="Expected a stable Agent 7 version"):
        normalize_version(version)


def test_update_agent_version_fails_when_a_pin_is_missing(tmp_path: Path) -> None:
    write_pins(tmp_path)
    (tmp_path / INSTALLER_PROVISION).write_text("remote-command: |\n    echo install\n")

    with pytest.raises(RuntimeError, match="exactly one Agent version pin"):
        update_agent_version(tmp_path, "7.82.3")
