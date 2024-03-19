# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from collections import defaultdict
import re
from packaging import version as version_module

# some monkey patching
def _parse_letter_version(letter, number):

    if letter:
        if number is None:
            number = 0

        return letter, int(number)
    if not letter and number:
        letter = "post"

        return letter, int(number)

    return None


version_module._parse_letter_version = _parse_letter_version  # pylint: disable=protected-access

RUBY_VERSION_PATTERN = r"""
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?                           # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<pre>                                          # pre-release
            [-_\.]?
            (?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview|appsec))
            [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>                                          # dev release
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
    )
    (?:[+ ](?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
"""

AGENT_VERSION_PATTERN = r"""
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?                           # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<pre>                                          # pre-release
            [-_\.]?
            (?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))
            [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>                                          # dev release
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
        (?P<devel>                                          # dev release
            -
            (?P<devel_l>devel)
            [ ]?
            (?P<devel_n>.*)?
        )?
    )
    (?:[\+\-](?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
"""


class Version(version_module.Version):
    @classmethod
    def build(cls, version, component):
        if isinstance(version, str):
            return cls(version, component)

        if isinstance(version, cls):
            return version

        raise TypeError(version)

    def __init__(self, version, component):

        self._component = component

        version = version.strip()

        pattern = version_module.VERSION_PATTERN

        if component == "ruby":
            pattern = RUBY_VERSION_PATTERN
            if version.startswith("* ddtrace"):
                version = re.sub(r"\* *ddtrace *\((.*)\)", r"\1", version)
            if version.startswith("* datadog"):
                version = re.sub(r"\* *datadog *\((.*)\)", r"\1", version)

        elif component == "libddwaf":
            if version.startswith("* libddwaf"):
                version = re.sub(r"\* *libddwaf *\((.*)\)", r"\1", version)

        elif component == "agent":
            version = re.sub(r"(.*) - Commit.*", r"\1", version)
            version = re.sub(r"(.*) - Meta.*", r"\1", version)
            version = re.sub(r"Agent (.*)", r"\1", version)
            version = re.sub("\x1b\\[\\d+m", "", version)  # remove color pattern from terminal
            version = re.sub(r"[a-zA-Z\-]*$", "", version)  # remove any lable post version

            pattern = AGENT_VERSION_PATTERN

        elif component == "java":
            version = version.split("~")[0]
            version = version.replace("-SNAPSHOT", "")

        elif component == "dotnet":
            version = re.sub(r"(datadog-dotnet-apm-)?(.*?)(\.tar\.gz)?", r"\2", version)

        elif component == "php":
            version = version.replace("-nightly", "")

        self._regex = re.compile(r"^\s*" + pattern + r"\s*$", re.VERBOSE | re.IGNORECASE)

        super().__init__(version)

    def __eq__(self, other):
        return super().__eq__(self.build(other, self._component))

    def __lt__(self, other):
        return super().__lt__(self.build(other, self._component))

    def __le__(self, other):
        return super().__le__(self.build(other, self._component))

    def __gt__(self, other):
        return super().__gt__(self.build(other, self._component))

    def __ge__(self, other):
        return super().__ge__(self.build(other, self._component))


class LibraryVersion:
    known_versions = defaultdict(set)

    def add_known_version(self, version, library=None):
        library = self.library if library is None else library
        LibraryVersion.known_versions[library].add(str(version))

    def __init__(self, library, version=None):
        self.library = None
        self.version = None

        if library is None:
            return

        if "@" in library:
            raise ValueError("Library can't contains '@'")

        self.library = library
        self.version = Version(version, component=library) if version else None
        self.add_known_version(self.version)

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.library}", "{self.version}")'

    def __str__(self):
        if not self.library:
            return str(None)

        return f"{self.library}@{self.version}" if self.version else self.library

    def __eq__(self, other):
        if not isinstance(other, str):
            raise TypeError(f"Can't compare LibraryVersion to type {type(other)}")

        if "@" in other:

            library, version = other.split("@", 1)
            self.add_known_version(library=library, version=version)

            if self.library != library:
                return False

            if self.version is None:
                raise ValueError("Weblog does not provide an library version number")

            return self.library == library and self.version == version

        library = other
        return self.library == library

    def _extract_members(self, other):
        if not isinstance(other, str):
            raise TypeError(f"Can't compare LibraryVersion to type {type(other)}")

        if "@" not in other:
            raise ValueError("Can't compare version numbers without a version")

        library, version = other.split("@", 1)

        if self.version is None and self.library == library:
            # the second comparizon is here because if it's not the good library,
            # the result will be always false, and nothing will be compared
            # on version. This use case ccan happens if a version is not provided
            # on other weblogs
            raise ValueError("Weblog does not provide an library version number")

        self.add_known_version(library=library, version=version)
        return library, version

    def __lt__(self, other):
        library, version = self._extract_members(other)
        return self.library == library and self.version < version

    def __le__(self, other):
        library, version = self._extract_members(other)
        return self.library == library and self.version <= version

    def __gt__(self, other):
        library, version = self._extract_members(other)
        return self.library == library and self.version > version

    def __ge__(self, other):
        library, version = self._extract_members(other)
        return self.library == library and self.version >= version

    def serialize(self):
        return {
            "library": self.library,
            "version": str(self.version),
        }
