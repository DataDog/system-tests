"""
This module provides utilities for working with APM libraries.
"""
import functools
from typing import Literal

import requests

import packaging.version


APMLibrary = Literal["python", "ruby", "java", "dotnet", "nodejs", "golang", "php", "cpp"]


@functools.lru_cache
def latest_version(library: APMLibrary) -> packaging.version.Version:
    """Return the latest version of the library specified.

    Result is cached to prevent unnecessary network requests and avoid rate limiting.
    """
    if library == "python":
        data = requests.get("https://pypi.org/pypi/ddtrace/json").json()
        versions = list(data["releases"].keys())
        versions.sort(key=packaging.version.parse, reverse=True)
        version = versions[0]
    elif library == "ruby":
        data = requests.get("https://rubygems.org/api/v1/versions/ddtrace.json").json()
        versions = [version["number"] for version in data]
        versions.sort(key=packaging.version.parse, reverse=True)
        version = versions[0]
    elif library == "java":
        data = requests.get(
            "https://search.maven.org/solrsearch/select?q=g:com.datadoghq+AND+a:dd-trace-api&rows=1&wt=json"
        ).json()
        versions = [version["latestVersion"] for version in data["response"]["docs"]]
        versions.sort(key=packaging.version.parse, reverse=True)
        version = versions[0]
    elif library == "dotnet":
        data = requests.get("https://api.nuget.org/v3-flatcontainer/datadog.trace/index.json").json()
        versions = list(data["versions"])
        versions.sort(key=packaging.version.parse, reverse=True)
        version = versions[0]
    elif library == "nodejs":
        data = requests.get("https://registry.npmjs.org/dd-trace").json()
        versions = list(data["versions"].keys())
        versions.sort(key=packaging.version.parse, reverse=True)
        version = versions[0]
    elif library == "golang":
        data = requests.get("https://proxy.golang.org/github.com/datadog/dd-trace-go/@latest")
        version = data.json()["Version"]
    elif library == "php":
        data = requests.get("https://packagist.org/packages/datadog/dd-trace.json").json()
        versions = list(data["package"]["versions"].keys())
        versions.sort(key=packaging.version.parse, reverse=True)
        version = versions[0]
    elif library == "cpp":
        raise NotImplementedError("cpp library not implemented")
    return packaging.version.parse(version)
