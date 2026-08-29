import re
from pathlib import Path

import pytest

from utils import scenarios


_BUN_IMAGE = re.compile(r"oven/bun(?P<reference>[^\s]*)")
_BUN_REFERENCE = re.compile(r":(?P<version>\d+\.\d+\.\d+)(?:-[A-Za-z0-9._-]+)?")
_MINIMUM_BUN_VERSION = (1, 4, 0)


def _bun_version(reference: str) -> tuple[int, int, int] | None:
    match = _BUN_REFERENCE.fullmatch(reference)
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.group("version").split("."))
    return major, minor, patch


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        (":1.3.13-alpine", (1, 3, 13)),
        (":1.4.0", (1, 4, 0)),
        (":latest", None),
        (":${BUN_VERSION}-alpine", None),
        (":1.3-alpine", None),
    ],
)
def test_bun_image_reference_requires_a_full_version(reference: str, expected: tuple[int, int, int] | None) -> None:
    assert _bun_version(reference) == expected


@scenarios.test_the_test
def test_nodejs_dockerfiles_avoid_vulnerable_bun_streaming_extraction() -> None:
    invalid_pins: list[str] = []
    dockerfiles = Path("utils/build/docker/nodejs").rglob("*Dockerfile")

    for dockerfile in sorted(dockerfiles):
        for match in _BUN_IMAGE.finditer(dockerfile.read_text(encoding="utf-8")):
            reference = match.group("reference")
            version = _bun_version(reference)
            if version is None:
                invalid_pins.append(f"{dockerfile}: unsupported Bun reference {reference}")
            elif version < _MINIMUM_BUN_VERSION:
                invalid_pins.append(f"{dockerfile}: Bun {'.'.join(str(part) for part in version)}")

    assert not invalid_pins, "Node.js Dockerfiles must pin Bun 1.4.0 or newer with a full version:\n" + "\n".join(
        invalid_pins
    )
