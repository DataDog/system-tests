from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest
from python.runfiles import runfiles

from bazel.parametric.configuration import language_configuration
from bazel.parametric.sharding import (
    file_hash,
    load_duration_manifest,
    membership_hash,
    pytest_split_arguments,
    round_robin_indices,
)
from utils.parametric.process import ProcessOutputRetention


_TEST_AGENT_LABEL = "//bazel/parametric:test_agent"


class _CollectedNodes:
    def __init__(
        self,
        output_directory: Path,
        duration_manifest: Path,
        shard_count: int,
        shard_index: int,
    ) -> None:
        self._output_directory = output_directory
        self._duration_manifest = duration_manifest
        self._shard_count = shard_count
        self._shard_index = shard_index

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        node_ids = sorted(item.nodeid for item in session.items)
        self._output_directory.joinpath("collected-nodes.txt").write_text(
            "".join(f"{node_id}\n" for node_id in node_ids), encoding="utf-8"
        )
        metadata = {
            "duration_manifest_hash": file_hash(self._duration_manifest),
            "membership_hash": membership_hash(node_ids),
            "selected_node_ids": node_ids,
            "shard_count": self._shard_count,
            "shard_number": self._shard_index + 1,
        }
        self._output_directory.joinpath("shard-metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


class _RoundRobinShard:
    def __init__(self, shard_count: int, shard_index: int) -> None:
        self._shard_count = shard_count
        self._shard_index = shard_index

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, config: pytest.Config, items: list[pytest.Item]) -> None:
        selected, deselected = round_robin_indices(len(items), self._shard_count, self._shard_index)
        deselected_items = [items[index] for index in deselected]
        items[:] = [items[index] for index in selected]
        config.hook.pytest_deselected(items=deselected_items)


def _assigned_port(name: str) -> int:
    mapping = json.loads(os.environ["ASSIGNED_PORTS"])
    suffix = f"{_TEST_AGENT_LABEL}:{name}"
    matches = [int(value) for key, value in mapping.items() if key.endswith(suffix)]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one assigned port ending in {suffix!r}, got {mapping!r}")
    return matches[0]


def _runfile(path: str) -> str:
    resolver = runfiles.Create()
    if resolver is None:
        raise RuntimeError("Bazel runfiles are unavailable")
    resolved = resolver.Rlocation(path)
    if resolved is None:
        raise FileNotFoundError(path)
    return resolved


def main() -> int:
    workspace = os.environ.get("TEST_WORKSPACE", "system_tests")
    configuration = language_configuration(os.environ["SYSTEM_TESTS_BAZEL_PARAMETRIC_LANGUAGE"])
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)

    os.environ.update(
        {
            "SYSTEM_TESTS_PARAMETRIC_RUNTIME": "process",
            "SYSTEM_TESTS_PROOT": _runfile("proot_static/usr/bin/proot.static"),
            "SYSTEM_TESTS_TEST_AGENT_BIN": _runfile(f"{workspace}/bazel/parametric/test_agent_bin"),
            "SYSTEM_TESTS_TEST_AGENT_APM_PORT": str(_assigned_port("apm")),
            "SYSTEM_TESTS_TEST_AGENT_OTLP_HTTP_PORT": str(_assigned_port("otlp_http")),
            "SYSTEM_TESTS_TEST_AGENT_OTLP_GRPC_PORT": str(_assigned_port("otlp_grpc")),
        }
    )
    os.environ[configuration.artifact_environment_variable] = _runfile(f"{workspace}/{configuration.artifact_runfile}")
    os.environ[configuration.version_environment_variable] = configuration.version

    shard_count = int(os.environ.get("TEST_TOTAL_SHARDS", "1"))
    shard_index = int(os.environ.get("TEST_SHARD_INDEX", "0"))
    duration_manifest = Path(_runfile(f"{workspace}/bazel/parametric/{configuration.duration_manifest}"))
    load_duration_manifest(duration_manifest)
    shard_status = os.environ.get("TEST_SHARD_STATUS_FILE")
    if shard_status:
        Path(shard_status).touch()

    arguments = [
        "--json-report-omit",
        "collectors",
        "warnings",
        "streams",
        "log",
        "keywords",
        "--scenario=PARAMETRIC",
        f"--library={configuration.library}",
        "--parametric-runtime=process",
        "-W",
        "ignore::DeprecationWarning:_pytest.assertion.rewrite",
        "--no-header",
        "-q",
        "tests/parametric",
    ]
    arguments.extend(sys.argv[1:])
    splitting_algorithm = os.environ.get("SYSTEM_TESTS_PARAMETRIC_SPLITTING_ALGORITHM", "least_duration")
    plugins: list[object] = []
    if splitting_algorithm == "round_robin":
        plugins.append(_RoundRobinShard(shard_count, shard_index))
    else:
        arguments.extend(
            pytest_split_arguments(
                shard_count,
                shard_index,
                duration_manifest,
                algorithm=splitting_algorithm,
            )
        )
    output_directory = Path(os.environ["TEST_UNDECLARED_OUTPUTS_DIR"])
    collector = _CollectedNodes(output_directory, duration_manifest, shard_count, shard_index)
    plugins.append(collector)
    plugins.append(ProcessOutputRetention(output_directory / "system-tests" / "outputs"))
    return int(pytest.main(arguments, plugins=plugins))


if __name__ == "__main__":
    sys.exit(main())
