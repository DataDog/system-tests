"""Test the instrumented process discovery mechanism feature."""

import pytest
import json
import msgpack
from jsonschema import validate as validation_jsonschema
from utils import features, scenarios


def find_dd_memfds(test_library, pid: int) -> list[str]:
    rc, out = test_library.container_exec_run(f"find /proc/{pid}/fd -lname '/memfd:datadog-tracer-info*'")
    if not rc:
        return []

    return out.split()


def validate_schema(payload: str) -> bool:
    schema = None
    with open("utils/interfaces/schemas/library/process-discovery.json", "r") as f:
        schema = json.load(f)

    try:
        validation_jsonschema(payload, schema)
        return True
    except Exception:
        return False


def read_memfd(test_library, memfd_path: str):
    rc, output = test_library.container_exec_run_raw(f"cat {memfd_path}")
    if not rc:
        return rc, output

    return rc, msgpack.unpackb(output)


@scenarios.parametric
@features.process_discovery
class Test_ProcessDiscovery:
    @pytest.mark.parametrize(
        "library_env",
        [
            {"DD_SERVICE": "a", "DD_ENV": "test", "DD_VERSION": "0.1.0"},
            {"DD_SERVICE": "b", "DD_ENV": "second-test", "DD_VERSION": "0.2.0"},
        ],
    )
    def test_metadata_content(self, test_library, library_env):
        """Verify the content of the memfd file matches the expected metadata format and structure"""
        with test_library:
            # NOTE(@dmehala): the server is started on container is always pid 1.
            # That's a strong assumption :hehe:
            # Maybe we should use `pidof pidof parametric-http-server` instead.
            memfds = find_dd_memfds(test_library, 1)
            assert len(memfds) == 1

            rc, tracer_metadata = read_memfd(test_library, memfds[0])
            assert rc
            assert validate_schema(tracer_metadata)

            assert tracer_metadata["schema_version"] == 1
            assert tracer_metadata["runtime_id"]
            # assert tracer_metadata["hostname"]
            # TODO(@dmehala): how to get the version?
            # assert tracer_metadata["tracer_version"] ==
            assert tracer_metadata["tracer_language"] == test_library.lang
            assert tracer_metadata["service_name"] == library_env["DD_SERVICE"]
            assert tracer_metadata["service_version"] == library_env["DD_VERSION"]
            assert tracer_metadata["service_env"] == library_env["DD_ENV"]
