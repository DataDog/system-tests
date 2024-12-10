# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from collections import defaultdict
import re
import semantic_version as version_module


def _build(version):
    if isinstance(version, str):
        return Version(version)

    if isinstance(version, Version):
        return version

    raise TypeError(version)


class Version(version_module.Version):
    def __init__(self, version=None, major=None, minor=None, patch=None, prerelease=None, build=None):
        if version is not None:
            # remove any leading "v"
            if version.startswith("v"):
                version = version[1:]

            # and use coerce to allow the wide variaty of version strings
            x = version_module.Version.coerce(version)
            major = x.major
            minor = x.minor
            patch = x.patch
            prerelease = x.prerelease
            build = x.build

        super().__init__(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)

    def __eq__(self, other):
        return super().__eq__(_build(other))

    def __lt__(self, other):
        return super().__lt__(_build(other))

    def __le__(self, other):
        return super().__le__(_build(other))

    def __gt__(self, other):
        return super().__gt__(_build(other))

    def __ge__(self, other):
        return super().__ge__(_build(other))


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

        if version:
            version = version.strip()

            if library == "ruby":
                # ruby version pattern can be like

                # 2.0.0.rc1 b908262
                # 2.0.0 b908262
                # 2.0.0.rc1
                #   rc1 is a pre-release, so we need to add a - sign
                #   b908262 is a build metadata, so we need to add a + sign

                # => adding + and - signs in the good places

                base = r"\d+\.\d+\.\d+"
                prerelease = r"[\w\d+]+"
                build = r"[a-f0-9]+"
                if re.match(rf"{base}[\. ]{prerelease}[\. ]{build}", version):
                    version = re.sub(rf"({base})[\. ]({prerelease})[\. ]({build})", r"\1-\2+\3", version)
                elif re.match(rf"{base}[\. ]{build}", version):
                    version = re.sub(rf"({base})[\. ]({build})", r"\1+\2", version)
                elif re.match(rf"{base}[\. ]{prerelease}", version):
                    version = re.sub(rf"({base})[\. ]({prerelease})", r"\1-\2", version)

            elif library == "libddwaf":
                if version.startswith("* libddwaf"):
                    version = re.sub(r"\* *libddwaf *\((.*)\)", r"\1", version)

            elif library == "java":
                version = version.split("~")[0]
                version = version.replace("-SNAPSHOT", "")

            elif library == "dotnet":
                version = re.sub(r"(datadog-dotnet-apm-)?(.*?)(\.tar\.gz)?", r"\2", version)

            elif library == "php":
                version = version.replace("-nightly", "")

            self.version = Version(version)

            if library == "ruby":
                if len(self.version.build) != 0 or len(self.version.prerelease) != 0:
                    # we are not in a released version

                    # dd-trace-rb main branch expose a version equal to the last release, so hack it:
                    # * add 1 to minor version
                    # * and set z as prerelease if not prerelease is set, becasue z will be after any other prerelease

                    # if dd-trace-rb repo fix the underlying issue, we can remove this hack.
                    self.version = Version(
                        major=self.version.major,
                        minor=self.version.minor,
                        patch=self.version.patch + 1,
                        prerelease=self.version.prerelease,
                        build=self.version.build,
                    )

                    if not self.version.prerelease:
                        self.version = Version(
                            major=self.version.major,
                            minor=self.version.minor,
                            patch=self.version.patch,
                            prerelease=("z",),
                            build=self.version.build,
                        )

            self.add_known_version(self.version)
        else:
            self.version = None

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.library}", "{self.version}")'

    def __str__(self):
        if not self.library:
            return str(None)

        return f"{self.library}@{self.version}" if self.version else self.library

    def __eq__(self, other):
        if isinstance(other, LibraryVersion):
            return self.library == other.library and self.version == other.version

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
        if isinstance(other, LibraryVersion):
            return other.library, other.version

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


if __name__ == "__main__":
    v = LibraryVersion("ruby", "  * ddtrace (0.53.0.appsec.180045)")
    assert str(v.version) == "0.53.1-appsec+180045"
