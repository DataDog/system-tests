from ._agent import AgentInterfaceValidator
from ._library.core import LibraryInterfaceValidator
from ._logs.core import _LibraryStdout, _LibraryDotnetManaged

# singletons
agent = AgentInterfaceValidator()
library = LibraryInterfaceValidator()
library_stdout = _LibraryStdout()
library_dotnet_managed = _LibraryDotnetManaged()

all = (agent, library, library_stdout, library_dotnet_managed)
