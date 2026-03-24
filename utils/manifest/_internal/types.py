from dataclasses import dataclass
from typing import NotRequired, TypedDict, Any

import semantic_version as semver

from .const import TestDeclaration


from semantic_version.base import AllOf, Never, Range, Version


# semver module offers two spec engine :
# 1. SimpleSpec : not a good fit because it does not allows OR clause
# 2. NpmSpec : not a good fit because it disallow prerelease version by default (6.0.0-pre is not in ">=5.0.0")
# So we use a custom one, based on NPM spec, allowing pre-release versions
class _CustomParser(semver.NpmSpec.Parser):
    # [CHANGED] Override range() to use PRERELEASE_ALWAYS policy on all clauses.
    # The library defaults to PRERELEASE_SAMEPATCH which excludes prereleases
    # from non-prerelease specs (e.g. 6.0.0-pre not in ">=5.0.0").
    @classmethod
    def range(cls, operator: Any, target: Any) -> semver.base.Range:  # noqa: ANN401
        return semver.base.Range(operator, target, prerelease_policy=semver.base.Range.PRERELEASE_ALWAYS)

    # [CHANGED] Override parse() to fix prerelease handling.
    # The library splits prerelease clauses into separate branches that break
    # alphabetical ordering (e.g. 2.7.0-rc.4 incorrectly matches "<2.7.0-dev").
    # Our version removes that split and uses clauses directly, relying on
    # PRERELEASE_ALWAYS from range() for correct semver comparison.
    @classmethod
    def parse(cls, expression: str) -> AllOf:
        result = Never()
        # [IDENTICAL] Split on || for OR groups
        groups = expression.split(cls.JOINER)
        for raw_group in groups:
            group = raw_group.strip() or ">=0.0.0"

            subclauses = []
            # [IDENTICAL] Hyphen range handling
            if cls.HYPHEN in group:
                low, high = group.split(cls.HYPHEN, 2)
                subclauses = cls.parse_simple(">=" + low) + cls.parse_simple("<=" + high)
            else:
                # [IDENTICAL] Block parsing and validation
                blocks = group.split(" ")
                for block in blocks:
                    if not cls.NPM_SPEC_BLOCK.match(block):
                        raise ValueError(f"Invalid NPM block in {expression!r}: {block!r}")
                    parsed = cls.parse_simple(block)
                    # [CHANGED] Caret upper bound: ^1.2.3 expands to >=1.2.3 <2.0.0.
                    # Replace <X.Y.Z with <X.Y.Z-0 so prereleases of the next major
                    # are excluded (e.g. 2.0.0-alpha not in ^1.2.3).
                    if block.startswith("^"):
                        for clause in parsed:
                            if clause.operator == Range.OP_LT and not clause.target.prerelease:
                                subclauses.append(
                                    cls.range(
                                        operator=Range.OP_LT,
                                        target=Version(
                                            major=clause.target.major,
                                            minor=clause.target.minor,
                                            patch=clause.target.patch,
                                            prerelease=("0",),
                                        ),
                                    )
                                )
                            else:
                                subclauses.append(clause)
                    else:
                        subclauses.extend(parsed)

            # [CHANGED] Use subclauses directly instead of the library's prerelease split.
            # The library separates prerelease/non-prerelease clauses and recombines them
            # with extra bounds, which breaks direct prerelease comparison.
            result |= AllOf(*subclauses)

        return result


class SemverRange(semver.NpmSpec):
    Parser = _CustomParser


@dataclass
class SkipDeclaration:
    """Type for skip declarations. Unlike TestDeclaration it also contains the details"""

    value: TestDeclaration
    details: str | None = None

    def __init__(self, value: str, details: str | None = None):
        self.value = TestDeclaration(value)
        self.details = details

    def __eq__(self, value: object, /) -> bool:
        if isinstance(value, SkipDeclaration):
            return self.value == value.value and self.details == value.details
        if isinstance(value, TestDeclaration):
            return self.value == value

        raise TypeError(f"Comparison between 'SkipDeclaration and {type(value)} is not supported")

    def __str__(self) -> str:
        return f"{self.value} ({self.details})" if self.details else f"{self.value}"

    def __hash__(self) -> int:
        return hash(str(self))


class Condition(TypedDict):
    """Type for deactivation conditions"""

    component: str
    component_version: NotRequired[SemverRange]
    excluded_component_version: NotRequired[SemverRange]
    weblog: NotRequired[list[str]]
    excluded_weblog: NotRequired[list[str]]
    declaration: SkipDeclaration


class ManifestData(dict[str, list[Condition]]):
    """A named dict[str, list[Condition]] to store manifest data
    Mapping with raw manifest data:
    --------------------------------------------------------
    -------------------------------------------------      |
    tests/dir/file.py::Class:                       |      |
    ------------------------------------            | rule |
        - weblog: weblog1              | Condition  |      |
          component_version: <4.3.5    |            |      |
          declaration: missing_feature |            |      | ManifestData
    -------------------------------------------------      |
    tests/dir/file.py::Class::func:                 |      |
    ------------------------------------            | rule |
        - weblog: weblog1              | Condition  |      |
          component_version: <4.3.5    |            |      |
          declaration: missing_feature |            |      |
    -------------------------------------------------      |
    --------------------------------------------------------
    """
