"""pytest plugin: runs a system-tests scenario's containers as Nix declares them.

The scenario's services (image, command, environment, mounts, ports, healthcheck, start order) are
declared in Nix (./module.nix and the scenario modules) and given to pytest as a JSON spec with
`--nix-services SPEC`. Once system-tests has configured the scenario, this plugin replaces each
container's configuration with the spec's. Starting, health-checking, stopping and collecting the
logs stay with system-tests, which reads the configuration only when it starts the containers.

system-tests still computes its own configuration first. The plugin compares it with the spec and
writes both, and their differences, to <logs>/nix-services/. A difference means system-tests changed
what it runs (or the spec is wrong): it is reported, and fails the run with --nix-services-strict. A
container system-tests starts that the spec lacks, or the other way round, always fails the run:
there is no configuration to give it.

Spec format (what ./module.nix writes):

    {"scenario": "DEFAULT", "services": {"<container name>": {
        "image": "name:tag", "command": str | [str] | null, "working_dir": str | null,
        "user": str | null, "environment": {"VAR": value}, "mounts": {"<target>": {"source": str, "mode": "ro"|"rw"}},
        "ports": {...}, "healthcheck": {...} | null, "security_opt": [str], "cap_add": [str],
        "privileged": bool, "network_aliases": [str], "depends_on": [str], "nix_store": bool}}}

Environment values are a string, null (unset) or {"file": path} (the file's contents). Mount
sources may start with @tests@ (the system-tests directory pytest runs in) or @logs@ (the
scenario's log folder). With nix_store, /nix/store is mounted read-only: the image holds no store
paths, it uses the mounted ones.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import pytest

_SECRET = re.compile(r"(API|APP)_KEY$")
_STORE_MOUNT = {"bind": "/nix/store", "mode": "ro"}


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("nix-services")
    group.addoption("--nix-services", metavar="SPEC", help="JSON spec of the scenario's services, from Nix")
    group.addoption(
        "--nix-services-strict",
        action="store_true",
        help="fail when system-tests' own configuration of a container differs from the spec",
    )


@pytest.hookimpl(trylast=True)  # after system-tests' conftest has configured the scenario
def pytest_configure(config: pytest.Config) -> None:
    spec_path = config.getoption("--nix-services")
    if not spec_path or config.option.collectonly or getattr(config.option, "replay", False):
        return

    from utils import context  # system-tests, importable once its conftest is loaded

    _Applier(config, context.scenario, json.loads(Path(spec_path).read_text())).run()


class _Applier:
    def __init__(self, config: pytest.Config, scenario: Any, spec: dict) -> None:
        self.config = config
        self.scenario = scenario
        self.spec = spec
        self.out_dir = Path(scenario.host_log_folder) / "nix-services"

    def run(self) -> None:
        if self.spec["scenario"] != self.scenario.name:
            pytest.exit(f"nix-services: the spec is for {self.spec['scenario']}, not {self.scenario.name}", 1)

        containers = {c.name: c for c in self.scenario._containers}  # noqa: SLF001
        services = self.spec["services"]
        if set(containers) != set(services):
            pytest.exit(
                "nix-services: system-tests starts "
                f"{sorted(containers)} for {self.scenario.name}, the spec declares {sorted(services)}",
                1,
            )

        upstream = {name: _snapshot(c) for name, c in containers.items()}
        for name, container in containers.items():
            self._apply(container, services[name], containers)
        applied = {name: _snapshot(c) for name, c in containers.items()}
        drift = {name: d for name in containers if (d := _diff(upstream[name], applied[name]))}

        # The store mount is how the spec's images work, not something to compare.
        for name, container in containers.items():
            if services[name]["nix_store"]:
                container.volumes["/nix/store"] = dict(_STORE_MOUNT)

        self.out_dir.mkdir(parents=True, exist_ok=True)
        for filename, data in (("system-tests.json", upstream), ("nix.json", applied), ("drift.json", drift)):
            (self.out_dir / filename).write_text(json.dumps(_masked(data), indent=2, sort_keys=True) + "\n")

        self._report(drift)
        if drift and self.config.getoption("--nix-services-strict"):
            pytest.exit(f"nix-services: system-tests' configuration differs from the spec, see {self.out_dir}", 1)

    def _apply(self, container: Any, service: dict, containers: dict) -> None:
        if _image_ref(service["image"]) != _image_ref(container.image.name):
            # system-tests loaded the image it wanted in configure(); load the spec's instead.
            from utils._context.containers import ImageInfo

            container.image = ImageInfo(service["image"], local_image_only=True)
            container.image.load()
            container.image.save_image_info(container.log_folder_path)

        container.command = service["command"]
        container.working_dir = service["working_dir"]
        container.user = service["user"]
        container.environment = {k: _resolve_env(v) for k, v in service["environment"].items()}
        container.volumes = {
            self._resolve_source(container, m["source"]): {"bind": target, "mode": m["mode"]}
            for target, m in service["mounts"].items()
        }
        container.ports = {k: tuple(v) if isinstance(v, list) else v for k, v in service["ports"].items()}
        container.healthcheck = service["healthcheck"]
        container.security_opt = service["security_opt"] or None
        container.cap_add = service["cap_add"] or None
        container.privileged = service["privileged"]
        container.network_aliases = service["network_aliases"]
        container.depends_on = [containers[name] for name in service["depends_on"]]

    def _resolve_source(self, container: Any, source: str) -> str:
        project = container.host_project_dir
        return source.replace("@logs@", f"{project}/{self.scenario.host_log_folder}").replace("@tests@", project)

    def _report(self, drift: dict) -> None:
        lines = [f"nix-services: {self.scenario.name} runs the services of {self.config.getoption('--nix-services')}"]
        if drift:
            lines.append(f"nix-services: system-tests' own configuration differs, see {self.out_dir}/drift.json:")
            for name, changes in drift.items():
                lines.extend(f"  {name}.{key}" for key in changes)
        reporter = self.config.pluginmanager.get_plugin("terminalreporter")
        for line in lines:
            if reporter is not None:
                reporter.write_line(line)
            else:
                print(line, file=sys.stderr)


def _resolve_env(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    if "file" in value:
        return Path(value["file"]).read_text()
    raise ValueError(f"nix-services: unknown environment value {value!r}")


def _image_ref(name: str) -> str:
    """name, with the tag Docker defaults to when it has none."""
    last = name.rsplit("/", 1)[-1]
    return name if ":" in last or "@" in last else f"{name}:latest"


def _snapshot(container: Any) -> dict:
    """What the container would run with, in a form that compares regardless of how it was set."""
    mounts = {}
    for source, mount in container.volumes.items():
        if source.startswith("./"):  # relative to the system-tests directory, see _fix_host_pwd_in_volumes
            source = f"{container.host_project_dir}{source[1:]}"
        mounts[os.path.normpath(mount["bind"])] = {
            "source": os.path.normpath(source),
            "mode": mount.get("mode", "rw"),
        }
    command = container.command
    return {
        "image": _image_ref(container.image.name),
        "command": shlex.split(command) if isinstance(command, str) else command,
        "working_dir": container.working_dir,
        "user": container.user,
        "environment": {k: None if v is None else str(v) for k, v in container.environment.items()},
        "mounts": mounts,
        "ports": json.loads(json.dumps(container.ports)),
        "healthcheck": container.healthcheck,
        "security_opt": sorted(container.security_opt or []),
        "cap_add": sorted(container.cap_add or []),
        "privileged": container.privileged,
        "network_aliases": sorted(container.network_aliases or []),
        "depends_on": sorted(d.name for d in container.depends_on),
    }


def _diff(upstream: dict, applied: dict) -> dict:
    result: dict[str, Any] = {}
    for key, ours in applied.items():
        theirs = upstream[key]
        if theirs == ours:
            continue
        if isinstance(theirs, dict) and isinstance(ours, dict) and key in ("environment", "mounts", "ports"):
            result[key] = {
                k: {"system-tests": theirs.get(k), "nix": ours.get(k)}
                for k in sorted(set(theirs) | set(ours))
                if theirs.get(k) != ours.get(k)
            }
        else:
            result[key] = {"system-tests": theirs, "nix": ours}
    return result


def _masked(data: Any, *, secret: bool = False) -> Any:
    """Masks the values of API and app keys (in drift.json, under the variable's name)."""
    if isinstance(data, dict):
        return {k: _masked(v, secret=secret or bool(_SECRET.search(k))) for k, v in data.items()}
    if isinstance(data, str) and secret:
        return "<masked>"
    return data
