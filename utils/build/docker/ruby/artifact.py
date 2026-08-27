from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import GitHubBranchResolver, RubygemsLatestResolver


class Dev(SimpleTarget):
    inputs = (
        GitHubBranchResolver(
            name="library_branch",
            repository="DataDog/dd-trace-rb",
            variable_name="LIBRARY_TARGET_BRANCH",
            default_value="master",
        ),
    )
    entries = (
        text_entry(
            "ruby-load-from-bundle-add",
            "gem 'datadog', require: 'datadog/auto_instrument', "
            "git: 'https://github.com/DataDog/dd-trace-rb.git', ref: '{library_branch.sha}'",
        ),
    )


class Prod(SimpleTarget):
    inputs = (RubygemsLatestResolver(name="datadog", package="datadog"),)
    entries = (
        text_entry(
            "ruby-load-from-bundle-add",
            "gem 'datadog', '{datadog.version}', require: 'datadog/auto_instrument'",
        ),
    )
