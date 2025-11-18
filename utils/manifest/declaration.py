from utils._decorators import CustomSpec as SemverRange
from utils._decorators import parse_skip_declaration
from collections.abc import Callable
from typing import Any
import re


class Declaration:
    reason_regex = r" ?(?:\((.*)\))?"
    skip_declaration_regex = rf"(bug|flaky|incomplete_test_app|irrelevant|missing_feature){reason_regex}"
    version_regex = r"(?:\d+\.\d+\.\d+|\d+\.\d+|\d+)[.+-]?[.\w+-]*"
    simple_regex = rf"(>|>=|v)?({version_regex}){reason_regex}"
    full_regex = rf"(v)?([^()]*){reason_regex}"

    def __init__(
        self,
        raw_declaration: str,
        *,
        is_inline: bool = False,
        semver_factory: type[SemverRange] | Callable[[str], Any] = SemverRange,
    ) -> None:
        if not raw_declaration:
            raise ValueError("raw_declaration must not be None or an empty string")
        self.raw = raw_declaration.strip()
        self.is_inline = is_inline
        self.semver_factory = semver_factory
        self.parse_declaration()

    @staticmethod
    def fix_separator(version: str) -> str:
        elements = re.fullmatch(r"(\d+\.\d+\.\d+)([.+-]?)([.\w+-]*)", version)
        if not elements or not elements.group(3):
            return version
        if not elements.group(2) or elements.group(2) == ".":
            sanitized_version = elements.group(1) + "-" + elements.group(3)
        else:
            sanitized_version = elements.group(1) + elements.group(2) + elements.group(3)
        return sanitized_version

    @staticmethod
    def fix_missing_minor_patch(version: str) -> str:
        for _ in range(2):
            if re.fullmatch(r"\d+\.\d+\.\d+.*", version):
                break
            version += ".0"
        return version

    transformations: list[Callable[[str], str]] = [fix_separator, fix_missing_minor_patch]

    @staticmethod
    def sanitize_version(version: str, transformations: list[Callable[[str], str]] | None = None) -> str:
        if transformations is None:
            transformations = Declaration.transformations
        matches = re.finditer(Declaration.version_regex, version)
        for match in matches:
            matched_section = version[match.start() : match.end()]
            for transformation in transformations:
                matched_section = transformation(matched_section)
            version = f"{version[:match.start()]}{matched_section}{version[match.end():]}"
        return version

    def parse_declaration(self) -> None:
        elements = re.fullmatch(self.skip_declaration_regex, self.raw, re.ASCII)
        if elements:
            self.is_skip = True
            skip_declaration = parse_skip_declaration(self.raw)
            self.value = skip_declaration[0]
            if elements[1]:
                self.reason = skip_declaration[1]
            return

        elements = re.fullmatch(self.full_regex, self.raw, re.ASCII)

        if not elements:
            raise ValueError(f"Wrong version format: {self.raw} (is inline: {self.is_inline})")

        self.is_skip = False
        raw_version = elements.group(2)
        if self.is_inline:
            if elements.group(1) == "v":
                raw_version = f">={raw_version}"
        sanitized_version = Declaration.sanitize_version(raw_version)

        self.value = self.semver_factory(sanitized_version)
        if elements.group(len(elements.groups()) - 1):
            self.reason = elements.group(len(elements.groups()) - 1)

    def __str__(self):
        if self.reason:
            return f"{self.value} ({self.reason})"
        return f"{self.value}"
