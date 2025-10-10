"""Test the instrumented process discovery mechanism feature."""

import pytest
import json
import msgpack
from jsonschema import validate as validation_jsonschema
from utils import features, scenarios, context, missing_feature
from utils._context.component_version import Version


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


def assert_v1(tracer_metadata, test_library, library_env):
    assert tracer_metadata["runtime_id"]
    # assert tracer_metadata["hostname"]

    lang = "go" if test_library.lang == "golang" else test_library.lang
    assert tracer_metadata["tracer_language"] == lang
    assert tracer_metadata["service_name"] == library_env["DD_SERVICE"]
    assert tracer_metadata["service_version"] == library_env["DD_VERSION"]
    assert tracer_metadata["service_env"] == library_env["DD_ENV"]

    version = Version(tracer_metadata["tracer_version"])
    assert version == get_context_tracer_version()


def assert_v2(tracer_metadata, test_library, library_env):
    assert_v1(tracer_metadata, test_library, library_env)
    if library_env["DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED"] == "true":
        assert "entrypoint.name" in tracer_metadata["process_tags"]
    elif library_env["DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED"] == "false":
        assert tracer_metadata["process_tags"] == ""
    assert tracer_metadata["container_id"] == ""


asserters = {1: assert_v1, 2: assert_v2}


def assert_metadata_content(test_library, library_env):
    # NOTE(@dmehala): the server is started on container is always pid 1.
    # That's a strong assumption :hehe:
    # Maybe we should use `pidof pidof parametric-http-server` instead.
    memfds = find_dd_memfds(test_library, 1)
    assert len(memfds) == 1

    rc, tracer_metadata = read_memfd(test_library, memfds[0])
    assert rc
    assert validate_schema(tracer_metadata)

    schema_version = tracer_metadata["schema_version"]
    assert_func = asserters.get(schema_version)
    assert assert_func, f"unsupported version {schema_version}"

    assert_func(tracer_metadata, test_library, library_env)


@scenarios.parametric
@features.process_discovery
class Test_ProcessDiscovery:
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SERVICE": "b",
                "DD_ENV": "second-test",
                "DD_VERSION": "0.2.0",
                "DD_AGENT_HOST": "localhost",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "false",
            }
        ],
    )
    def test_metadata_content_without_process_tags(self, test_library, library_env):
        """Verify the content of the memfd file matches the expected metadata format and structure"""
        with test_library:
            assert_metadata_content(test_library, library_env)

    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    @pytest.mark.parametrize(
        "library_env",
        [
            {
                "DD_SERVICE": "a",
                "DD_ENV": "test",
                "DD_VERSION": "0.1.0",
                # DD_AGENT_HOST set to localhost as dd-trace-go tracer fails to init if agent is set on another host and the tracer can't connect
                "DD_AGENT_HOST": "localhost",
                "DD_EXPERIMENTAL_PROPAGATE_PROCESS_TAGS_ENABLED": "true",
            }
        ],
    )
    def test_metadata_content_with_process_tags(self, test_library, library_env):
        """Verify the content of the memfd file matches the expected metadata format and structure"""
        with test_library:
            assert_metadata_content(test_library, library_env)
