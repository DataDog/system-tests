# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from packaging.version import parse as parse_version


class Version:
    """ Version object that supports comparizon with string"""

    def __init__(self, version) -> None:
        self._version = parse_version(version)

    @staticmethod
    def __test__():
        v = Version("1.0")

        assert v == "1.0"
        assert v != "1.1"

        assert v <= "1.1"
        assert v <= "1.0"
        assert "1.1" >= v
        assert "1.0" >= v

        assert v < "1.1"
        assert "1.1" > v

        assert v >= "0.9"
        assert v >= "1.0"
        assert "0.9" <= v
        assert "1.0" <= v

        assert v > "0.9"
        assert "0.9" < v

        v = Version("0.53.0.dev70+g494e6dc0")

        assert v == "0.53.0.dev70+g494e6dc0"

    def __eq__(self, other):
        return self._version == parse_version(other)

    def __lt__(self, other):
        return self._version < parse_version(other)

    def __le__(self, other):
        return self._version <= parse_version(other)

    def __gt__(self, other):
        return self._version > parse_version(other)

    def __ge__(self, other):
        return self._version >= parse_version(other)

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
        self.version = Version(version) if version else None

    @staticmethod
    def __test__():
        v = LibraryVersion("p")
        assert v == "p"
        assert v != "u"

        v = LibraryVersion("p", "1.0")

        assert v == "p@1.0"
        assert v == "p"
        assert v != "p@1.1"
        assert v != "u"

        assert v <= "p@1.1"
        assert v <= "p@1.0"
        assert "p@1.1" >= v
        assert "p@1.0" >= v

        assert v < "p@1.1"
        assert "p@1.1" > v

        assert v >= "p@0.9"
        assert v >= "p@1.0"
        assert "p@0.9" <= v
        assert "p@1.0" <= v

        assert v > "p@0.9"
        assert "p@0.9" < v

        assert (v <= "u@1.0") is False
        assert (v >= "u@1.0") is False

        assert ("u@1.0" <= v) is False
        assert ("u@1.0" >= v) is False

        v = LibraryVersion("p")

        assert ("u@1.0" == v) is False
        assert ("u@1.0" <= v) is False

        v = LibraryVersion("python", "0.53.0.dev70+g494e6dc0")

        assert v == "python@0.53.0.dev70+g494e6dc0"

        print("LibraryVersion is working as expected")

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


if __name__ == "__main__":
    Version.__test__()
    LibraryVersion.__test__()
