"""Flag selection for the mocked FFE rules-based configuration endpoint.

Mirrors the production endpoint: a valid selection serves only the flags it selects, and a selection that cannot be
applied serves every flag and names the reason in the DD-Flag-Selection-Ignored response header. The shared
ffe-system-test-data vectors in flag-selection/selection-vectors.json define the semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import TYPE_CHECKING
from urllib.parse import unquote_to_bytes, urlencode

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path


SELECTED_FLAG_TAGS = "selected_flag_tags"
SELECTED_FLAG_KEY_PATTERNS = "selected_flag_key_patterns"
FLAG_SELECTION_IGNORED_HEADER = "DD-Flag-Selection-Ignored"
# Limits from flag-selection/README.md in DataDog/ffe-system-test-data.
MAX_VALUES = 31
MAX_VALUE_BYTES = 200
FORCED_REASON_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,64}")

# The Unicode White_Space property. str.strip() would also remove U+001C..U+001F, which production keeps.
_WHITE_SPACE = "".join(
    chr(code_point)
    for code_point in (
        *range(0x09, 0x0E),
        0x20,
        0x85,
        0xA0,
        0x1680,
        *range(0x2000, 0x200B),
        0x2028,
        0x2029,
        0x202F,
        0x205F,
        0x3000,
    )
)
_INVALID_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")


class SelectionIgnoredError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Selection:
    tags: tuple[str, ...]
    key_patterns: tuple[str, ...]

    def is_empty(self) -> bool:
        return not self.tags and not self.key_patterns

    def digest(self) -> str:
        canonical = urlencode(
            [(SELECTED_FLAG_KEY_PATTERNS, _utf8(value)) for value in self.key_patterns]
            + [(SELECTED_FLAG_TAGS, _utf8(value)) for value in self.tags]
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _raw_bytes(value: str) -> bytes:
    # http.server decodes the request line as ISO-8859-1, so this restores the bytes on the wire.
    try:
        return value.encode("latin-1")
    except UnicodeEncodeError:
        return value.encode("utf-8")


def _query_unescape(value: str) -> str:
    """Decode like Go's url.QueryUnescape: '+' is a space and a '%' must start a two-digit hex escape."""
    if _INVALID_ESCAPE.search(value):
        raise ValueError("invalid percent-escape")
    return unquote_to_bytes(_raw_bytes(value.replace("+", " "))).decode("utf-8", "surrogateescape")


def _utf8(value: str) -> bytes:
    """The value's bytes on the wire, including bytes that are not valid UTF-8."""
    return value.encode("utf-8", "surrogateescape")


def _parameter_name(pair: str) -> str | None:
    try:
        return _query_unescape(pair.partition("=")[0])
    except ValueError:
        return None


def is_selection_parameter(pair: str) -> bool:
    return _parameter_name(pair) in {SELECTED_FLAG_TAGS, SELECTED_FLAG_KEY_PATTERNS}


def has_selection_parameters(raw_query: str) -> bool:
    return any(is_selection_parameter(pair) for pair in raw_query.split("&"))


def _normalize(values: Iterable[str]) -> tuple[str, ...]:
    trimmed = {value.strip(_WHITE_SPACE) for value in values}
    trimmed.discard("")
    return tuple(sorted(trimmed, key=_utf8))


def parse_selection(raw_query: str) -> Selection:
    """Parse the raw query as http.server receives it.

    Raise SelectionIgnoredError with the first reason, in the documented precedence, that ignores the selection.
    """
    raw: dict[str, list[str]] = {SELECTED_FLAG_TAGS: [], SELECTED_FLAG_KEY_PATTERNS: []}
    for pair in raw_query.split("&"):
        name = _parameter_name(pair)
        if name not in raw:
            continue
        try:
            raw[name].append(_query_unescape(pair.partition("=")[2]))
        except ValueError:
            raise SelectionIgnoredError("malformed_selection") from None

    selection = Selection(
        tags=_normalize(raw[SELECTED_FLAG_TAGS]), key_patterns=_normalize(raw[SELECTED_FLAG_KEY_PATTERNS])
    )
    if len(selection.tags) > MAX_VALUES or len(selection.key_patterns) > MAX_VALUES:
        raise SelectionIgnoredError("too_many_values")
    if any(len(_utf8(pattern)) > MAX_VALUE_BYTES for pattern in selection.key_patterns):
        raise SelectionIgnoredError("invalid_key_pattern")
    if any(len(_utf8(tag)) > MAX_VALUE_BYTES for tag in selection.tags):
        raise SelectionIgnoredError("invalid_tag")
    return selection


def match_key_pattern(pattern: str, key: str) -> bool:
    """'*' matches any run of characters, including none; every other character is literal."""
    parts = pattern.split("*")
    if len(parts) == 1:
        return pattern == key
    first, *middle, last = parts
    if len(key) < len(first) + len(last) or not key.startswith(first) or not key.endswith(last):
        return False
    # Leftmost matching of the middle literals is enough: a later occurrence leaves less room for the rest.
    remaining = key[len(first) : len(key) - len(last)]
    for part in middle:
        index = remaining.find(part)
        if index < 0:
            return False
        remaining = remaining[index + len(part) :]
    return True


def select_flags(selection: Selection, flag_tags: Mapping[str, Sequence[str]]) -> list[str]:
    """Return the sorted keys selected among flag_tags, which maps every served flag key to its tags."""
    wanted = set(selection.tags)
    return sorted(
        key
        for key, tags in flag_tags.items()
        if selection.is_empty()
        or not wanted.isdisjoint(tags)
        or any(match_key_pattern(pattern, key) for pattern in selection.key_patterns)
    )


def load_flag_tags(path: Path) -> dict[str, list[str]]:
    """Tags per flag key from an evaluation suite's flag-tags.json. A flag that is not listed has no tags."""
    fixture = json.loads(path.read_text(encoding="utf-8"))
    return {flag["key"]: list(flag["tags"]) for flag in fixture["flags"]}


def validate_forced_reason(reason: object) -> str | None:
    if reason is None:
        return None
    if not isinstance(reason, str) or FORCED_REASON_PATTERN.fullmatch(reason) is None:
        raise ValueError("ignored_reason must be null or a token of letters, digits, '_', '.', or '-'")
    return reason
