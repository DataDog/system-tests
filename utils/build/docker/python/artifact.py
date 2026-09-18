from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import GitHubBranchResolver, PypiLatestResolver


class Dev(SimpleTarget):
    inputs = (
        GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-py",
            variable_name="LIBRARY_TARGET_BRANCH",
            default_value="main",
        ),
    )
    entries = (text_entry("python-load-from-s3", "{library_branch.sha}"),)


class Prod(SimpleTarget):
    inputs = (PypiLatestResolver(name="ddtrace", package="ddtrace"),)
    entries = (text_entry("python-load-from-pip", "ddtrace=={ddtrace.version}"),)
