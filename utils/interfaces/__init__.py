# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from ._agent import AgentInterfaceValidator
from ._backend import _BackendInterfaceValidator
from ._library.core import LibraryInterfaceValidator
from ._logs import _LibraryStdout, _LibraryDotnetManaged, _AgentStdout
from ._open_telemetry import OpenTelemetryInterfaceValidator

# singletons
agent = AgentInterfaceValidator()
library = LibraryInterfaceValidator()
library_stdout = _LibraryStdout()
agent_stdout = _AgentStdout()
library_dotnet_managed = _LibraryDotnetManaged()
backend = _BackendInterfaceValidator()
open_telemetry = OpenTelemetryInterfaceValidator()

all_interfaces = (agent, library, library_stdout, library_dotnet_managed, agent_stdout, backend)
