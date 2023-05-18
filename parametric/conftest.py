import base64
import contextlib
import dataclasses
import os
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Callable, Dict, Generator, List, Literal, TextIO, Tuple, TypedDict, Union
import urllib.parse

import requests
import pytest

from utils.parametric.spec.trace import V06StatsPayload
from utils.parametric.spec.trace import Trace
from utils.parametric.spec.trace import decode_v06_stats
from utils.parametric._library_client import APMLibraryClientGRPC
from utils.parametric._library_client import APMLibraryClientHTTP
from utils.parametric._library_client import APMLibrary
from tests.parametric.conftest import (
    test_id,
    AgentRequest,
    AgentRequestV06Stats,
    _request_token,
    APMLibraryTestServer,
    library_env,
    node_library_factory,
    python_library_factory,
    python_http_library_factory,
    golang_library_factory,
    dotnet_library_factory,
    java_library_factory,
    php_library_factory,
    ruby_library_factory,
    get_open_port,
    pytest_runtest_makereport,
    test_server_log_file,
    test_server,
    _TestAgentAPI,
    docker_run,
    docker,
    docker_network_log_file,
    docker_network_name,
    docker_network,
    test_agent_port,
    test_agent_log_file,
    test_agent_container_name,
    test_agent,
    test_server_timeout,
    test_library,
)


@pytest.fixture(autouse=True)
def skip_library(request, apm_test_server):
    overrides = set([s.strip() for s in os.getenv("OVERRIDE_SKIPS", "").split(",")])
    for marker in request.node.iter_markers("skip_library"):
        skip_library = marker.args[0]
        reason = marker.args[1]

        # Have to use `originalname` since `name` will contain the parameterization
        # eg. test_case[python]
        if apm_test_server.lang == skip_library and request.node.originalname not in overrides:
            pytest.skip("skipped {} on {}: {}".format(request.function.__name__, apm_test_server.lang, reason))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "snapshot(*args, **kwargs): mark test to run as a snapshot test which sends traces to the test agent"
    )
    config.addinivalue_line("markers", "skip_library(library, reason): skip test for library")


ClientLibraryServerFactory = Callable[[Dict[str, str]], APMLibraryTestServer]

_libs = {
    "dotnet": dotnet_library_factory,
    "golang": golang_library_factory,
    "java": java_library_factory,
    "nodejs": node_library_factory,
    "php": php_library_factory,
    "python": python_library_factory,
    "python_http": python_http_library_factory,
    "ruby": ruby_library_factory,
}
_enabled_libs: List[Tuple[str, ClientLibraryServerFactory]] = []
for _lang in os.getenv("CLIENTS_ENABLED", "dotnet,golang,java,nodejs,php,python,python_http,ruby").split(","):
    if _lang not in _libs:
        raise ValueError("Incorrect client %r specified, must be one of %r" % (_lang, ",".join(_libs.keys())))
    _enabled_libs.append((_lang, _libs[_lang]))


@pytest.fixture(
    params=list(factory for lang, factory in _enabled_libs), ids=list(lang for lang, factory in _enabled_libs)
)
def apm_test_server(request, library_env, test_id):
    # Have to do this funky request.param stuff as this is the recommended way to do parametrized fixtures
    # in pytest.
    apm_test_library = request.param

    yield apm_test_library(library_env, test_id, get_open_port())
