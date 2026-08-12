from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest
from python.runfiles import runfiles

from bazel.parametric.sharding import pytest_split_arguments


_TEST_AGENT_LABEL = "//bazel/parametric:test_agent"


class _CollectedNodes:
    def __init__(self, output_path: Path) -> None:
        self._output_path = output_path

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        node_ids = sorted(item.nodeid for item in session.items)
        self._output_path.write_text("".join(f"{node_id}\n" for node_id in node_ids))


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
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)

    os.environ.update(
        {
            "SYSTEM_TESTS_PARAMETRIC_RUNTIME": "process",
            "SYSTEM_TESTS_GO_LIBRARY_VERSION": "v2.4.0",
            "SYSTEM_TESTS_GO_PARAMETRIC_SERVER": _runfile(
                f"{workspace}/utils/build/docker/golang/parametric/go_parametric_server_/go_parametric_server"
            ),
            "SYSTEM_TESTS_PROOT": _runfile("proot_static/usr/bin/proot.static"),
            "SYSTEM_TESTS_TEST_AGENT_BIN": _runfile(f"{workspace}/bazel/parametric/test_agent_bin"),
            "SYSTEM_TESTS_TEST_AGENT_APM_PORT": str(_assigned_port("apm")),
            "SYSTEM_TESTS_TEST_AGENT_OTLP_HTTP_PORT": str(_assigned_port("otlp_http")),
            "SYSTEM_TESTS_TEST_AGENT_OTLP_GRPC_PORT": str(_assigned_port("otlp_grpc")),
        }
    )

    shard_count = int(os.environ.get("TEST_TOTAL_SHARDS", "1"))
    shard_index = int(os.environ.get("TEST_SHARD_INDEX", "0"))
    shard_status = os.environ.get("TEST_SHARD_STATUS_FILE")
    if shard_status:
        Path(shard_status).touch()

    arguments = [
        "--scenario=PARAMETRIC",
        "--library=golang",
        "--parametric-runtime=process",
        "--no-header",
        "-q",
        "tests/parametric",
    ]
    arguments.extend(pytest_split_arguments(shard_count, shard_index))
    output_directory = Path(os.environ["TEST_UNDECLARED_OUTPUTS_DIR"])
    return int(pytest.main(arguments, plugins=[_CollectedNodes(output_directory / "collected-nodes.txt")]))


if __name__ == "__main__":
    sys.exit(main())
