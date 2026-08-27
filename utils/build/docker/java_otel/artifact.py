from __future__ import annotations


from utils.target_artifacts.entry_helpers import text_entry
from utils.target_artifacts.models import SimpleTarget
from utils.target_artifacts.resolvers import GitHubLatestReleaseResolver

REPOSITORY = "open-telemetry/opentelemetry-java-instrumentation"


class Dev(SimpleTarget):
    inputs = (GitHubLatestReleaseResolver(name="release", repository=REPOSITORY),)
    entries = (text_entry("java-otel-load-from-release", "{release.tag_name}"),)


class Prod(Dev):
    pass
