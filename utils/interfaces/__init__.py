# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from ._agent import AgentInterfaceValidator
from ._backend_legacy import _BackendLegacyInterfaceValidator
from ._mocked_backend import _MockedBackendInterfaceValidator
from ._library.core import LibraryInterfaceValidator
from ._core import ProxyBasedInterfaceValidator
from ._logs import (
    _LibraryStdout,
    _LibraryDotnetManaged,
    _AgentStdout,
    _PostgresStdout,
    _LibraryStdout as LibraryStdoutInterface,
    _StdoutLogsInterfaceValidator as StdoutLogsInterface,
)
from ._open_telemetry import OpenTelemetryInterfaceValidator
from ._test_agent import _TestAgentInterfaceValidator

# singletons
agent = AgentInterfaceValidator()
library = LibraryInterfaceValidator("library")
library_stdout = _LibraryStdout()
agent_stdout = _AgentStdout()
library_dotnet_managed = _LibraryDotnetManaged()
backend_legacy = _BackendLegacyInterfaceValidator(library_interface=library)
mocked_backend = _MockedBackendInterfaceValidator()
open_telemetry = OpenTelemetryInterfaceValidator()
otel_collector = ProxyBasedInterfaceValidator("otel_collector")
postgres = _PostgresStdout()
test_agent = _TestAgentInterfaceValidator()

python_buddy = LibraryInterfaceValidator("python_buddy")
nodejs_buddy = LibraryInterfaceValidator("nodejs_buddy")
java_buddy = LibraryInterfaceValidator("java_buddy")
ruby_buddy = LibraryInterfaceValidator("ruby_buddy")
golang_buddy = LibraryInterfaceValidator("golang_buddy")

__all__ = [
    "LibraryStdoutInterface",
    "StdoutLogsInterface",
    "agent",
    "agent_stdout",
    "backend_legacy",
    "golang_buddy",
    "java_buddy",
    "library",
    "library_dotnet_managed",
    "library_stdout",
    "mocked_backend",
    "nodejs_buddy",
    "open_telemetry",
    "postgres",
    "python_buddy",
    "ruby_buddy",
    "test_agent",
]
