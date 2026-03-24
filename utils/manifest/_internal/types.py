from dataclasses import dataclass
from typing import NotRequired, TypedDict, Any

import semantic_version as semver

from .const import TestDeclaration


from semantic_version.base import AllOf, Never, Range


# semver module offers two spec engine :
# 1. SimpleSpec : not a good fit because it does not allows OR clause
# 2. NpmSpec : not a good fit because it disallow prerelease version by default (6.0.0-pre is not in ">=5.0.0")
# So we use a custom one, based on NPM spec, allowing pre-release versions
class _CustomParser(semver.NpmSpec.Parser):
    @classmethod
    def range(cls, operator: Any, target: Any) -> semver.base.Range:  # noqa: ANN401
        return semver.base.Range(operator, target, prerelease_policy=semver.base.Range.PRERELEASE_ALWAYS)

    @classmethod
    def parse(cls, expression: str) -> AllOf:
        result = Never()
        groups = expression.split(cls.JOINER)
        for raw_group in groups:
            group = raw_group.strip() or ">=0.0.0"

            subclauses = []
            if cls.HYPHEN in group:
                low, high = group.split(cls.HYPHEN, 2)
                subclauses = cls.parse_simple(">=" + low) + cls.parse_simple("<=" + high)
            else:
                blocks = group.split(" ")
                for block in blocks:
                    if not cls.NPM_SPEC_BLOCK.match(block):
                        raise ValueError(f"Invalid NPM block in {expression!r}: {block!r}")
                    subclauses.extend(cls.parse_simple(block))

            non_prerel_clauses = []
            for clause in subclauses:
                if clause.target.prerelease:
                    if clause.operator in (Range.OP_GT, Range.OP_GTE):
                        non_prerel_clauses.append(cls.range(operator=Range.OP_GTE, target=clause.target.truncate()))
                    elif clause.operator in (Range.OP_LT, Range.OP_LTE):
                        non_prerel_clauses.append(clause)
                else:
                    non_prerel_clauses.append(clause)
            result |= AllOf(*non_prerel_clauses)

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
