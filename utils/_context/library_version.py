# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from packaging.version import Version as BaseVersion, InvalidVersion
import re


def _build_version(version):
    if isinstance(version, str):
        return Version(version)
    elif isinstance(version, Version):
        return version
    else:
        raise TypeError(version)


class Version:
    """ Version object that supports comparizon with string"""

    def __init__(self, version, component=None):
        # some cleanup to handle the variaty of versions numbers

        if component == "ruby":
            version = version.strip()
            if version.startswith("* ddtrace"):

                version = re.sub(r"\* *ddtrace *\((\d+\.\d+\.\d+).*", r"\1", version)

        try:
            self._version = BaseVersion(version)
        except InvalidVersion:
            if "-" in version:
                self._version = BaseVersion(version.split("-")[0])
            else:
                raise

    def __eq__(self, other):
        return self._version == _build_version(other)._version

    def __lt__(self, other):
        return self._version < _build_version(other)._version

    def __le__(self, other):
        return self._version <= _build_version(other)._version

    def __gt__(self, other):
        return self._version > _build_version(other)._version

    def __ge__(self, other):
        return self._version >= _build_version(other)._version

    def __str__(self):
        return str(self._version)

    def __repr__(self):
        return repr(self._version)


class LibraryVersion:
    def __init__(self, library, version=None):
        if library is None:
            raise ValueError("Library can't be none")

        if "@" in library:
            raise ValueError("Library can't contains '@'")

        self.library = library
        self.version = Version(version, component=library) if version else None

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.library}", "{self.version}")'

    def __str__(self):
        return f"{self.library}@{self.version}" if self.version else self.library

    def __eq__(self, other):
        if not isinstance(other, str):
            raise TypeError(f"Can't compare LibraryVersion to type {type(other)}")

        if "@" in other:

            library, version = other.split("@", 1)

            if self.library != library:
                return False

            if self.version is None:
                raise ValueError("Weblog does not provide an library version number")

            return self.library == library and self.version == version
        else:
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
