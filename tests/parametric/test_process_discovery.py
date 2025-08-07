"""Test the instrumented process discovery mechanism feature."""

import os
import re
import pytest
import json
import msgpack
from jsonschema import validate as validation_jsonschema
from utils import features, scenarios, context
from utils._context.component_version import Version


def find_dd_memfds(test_library) -> list[str]:
    # We don't know the pid of the process we're instrumenting, so we need to
    # search for the memfd file in all running processes. We're in a container
    # so we only have processes involved in the test so this should be safe.
    #
    # Get a list of running pids first and then check the fds for each of them,
    # since running find on the entire /proc directory errors out without
    # returning any results.
    _, out = test_library.container_exec_run("ls /proc")
    # Ignore return code since it could fail if files disappear mid-way
    if not out:
        return []

    for pid in out.split():
        if not pid.isdigit():
            continue

        base = f"/proc/{pid}/fd"
        _, ls = test_library.container_exec_run(f"ls -l {base}")
        if not ls:
            continue

        found = []
        for line in ls.splitlines():
            # lrwx------ 1 root root 64 Aug 11 11:59 141 -> /memfd:datadog-tracer-info-VtF1ucAJ (deleted)
            match = re.search(r"(\d+) -> (.*)", line)
            if not match:
                continue

            fd = match.group(1)
            target = match.group(2)

            if target.startswith("/memfd:datadog-tracer-info"):
                found.append(os.path.join(base, fd))

        return found

    return []


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


def get_context_tracer_version():
    # Temporary fix for Ruby until we start to bump the version after a release
    # This cancels a hack in system-tests framework that increments the patch version
    # and add -dev to the version string.
    if context.library.name == "ruby":
        major = context.library.version.major
        minor = context.library.version.minor
        if "dev" in context.library.version.prerelease:
            patch = context.library.version.patch - 1
        else:
            patch = context.library.version.patch
        return Version(f"{major}.{minor}.{patch}")
    else:
        return context.library.version


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
            memfds = find_dd_memfds(test_library)
            assert len(memfds) == 1

            rc, tracer_metadata = read_memfd(test_library, memfds[0])
            assert rc
            assert validate_schema(tracer_metadata)

            assert tracer_metadata["schema_version"] == 1
            assert tracer_metadata["runtime_id"]
            # assert tracer_metadata["hostname"]

            lang = "go" if test_library.lang == "golang" else test_library.lang
            assert tracer_metadata["tracer_language"] == lang
            assert tracer_metadata["service_name"] == library_env["DD_SERVICE"]
            assert tracer_metadata["service_version"] == library_env["DD_VERSION"]
            assert tracer_metadata["service_env"] == library_env["DD_ENV"]

            version = Version(tracer_metadata["tracer_version"])
            assert version == get_context_tracer_version()
