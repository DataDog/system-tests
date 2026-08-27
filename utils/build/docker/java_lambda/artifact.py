from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import ArtifactEntry, SimpleTarget
from utils.target_artifacts.resolvers import GitHubBranchResolver, GitHubLatestReleaseResolver


class Dev(SimpleTarget):
    inputs = (
        GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-java",
            variable_name="LIBRARY_TARGET_BRANCH",
            default_value="master",
        ),
    )
    entries = (text_entry("java-load-from-s3", "{library_branch.sha}"),)


class Prod(SimpleTarget):
    inputs = (GitHubLatestReleaseResolver(name="release", repository="DataDog/dd-trace-java"),)
    entries = (text_entry("java-load-from-release", "{release.tag_name}"),)
