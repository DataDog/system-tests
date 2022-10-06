# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from ._core import current_test
from ._agent.core import AgentInterfaceValidator
from ._library.core import LibraryInterfaceValidator
from ._logs.core import _LibraryStdout, _LibraryDotnetManaged
from ._backend.core import _BackendInterfaceValidator


# singletons
agent = AgentInterfaceValidator()
library = LibraryInterfaceValidator()
library_stdout = _LibraryStdout()
library_dotnet_managed = _LibraryDotnetManaged()
backend = _BackendInterfaceValidator()

all_interfaces = (agent, library, library_stdout, library_dotnet_managed, backend)
