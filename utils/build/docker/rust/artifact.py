from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import CratesLatestResolver, GitHubBranchResolver


class Dev(SimpleTarget):
    inputs = (
        GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-rs",
            variable_name="LIBRARY_TARGET_BRANCH",
            default_value="main",
        ),
    )
    entries = (text_entry("rust-load-from-git", "{library_branch.sha}"),)


class Prod(SimpleTarget):
    inputs = (
        CratesLatestResolver(
            name="datadog_opentelemetry",
            package="datadog-opentelemetry",
        ),
    )
    entries = (text_entry("rust-load-from-crates", "{datadog_opentelemetry.version}"),)
