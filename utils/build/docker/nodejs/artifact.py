from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import GitHubBranchResolver, NpmLatestResolver


class Dev(SimpleTarget):
    inputs = (
        GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-js",
            variable_name="LIBRARY_TARGET_BRANCH",
            default_value="master",
        ),
    )
    entries = (text_entry("nodejs-load-from-npm", "DataDog/dd-trace-js#{library_branch.sha}"),)


class Prod(SimpleTarget):
    inputs = (NpmLatestResolver(name="dd-trace", package="dd-trace"),)
    entries = (text_entry("nodejs-load-from-npm", "dd-trace@{dd-trace.version}"),)
