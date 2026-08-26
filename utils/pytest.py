"""Approved pytest API for system tests.

Test modules should import this facade with ``from utils import pytest``.
The facade intentionally exposes only the pytest APIs used by this repository.
In particular, force-skip markers are available only through the semantic
decorators exported by :mod:`utils`.
"""

import pytest as _pytest  # noqa: PT013 - keep the underlying pytest module private


Config = _pytest.Config
FixtureRequest = _pytest.FixtureRequest
Item = _pytest.Item
Mark = _pytest.Mark
MarkDecorator = _pytest.MarkDecorator
MonkeyPatch = _pytest.MonkeyPatch
CaptureFixture = _pytest.CaptureFixture
Session = _pytest.Session
CallInfo = _pytest.CallInfo

approx = _pytest.approx
exit = _pytest.exit  # noqa: A001 - preserve the public pytest API name
fail = _pytest.fail
fixture = _pytest.fixture
param = _pytest.param
raises = _pytest.raises
skip = _pytest.skip
hookimpl = _pytest.hookimpl


class _AllowedMarks:
    """Pytest markers approved for direct use by system tests."""

    features = _pytest.mark.features
    parametrize = _pytest.mark.parametrize
    scenario = _pytest.mark.scenario
    xfail = _pytest.mark.xfail


mark = _AllowedMarks()

__all__ = [
    "CallInfo",
    "Config",
    "FixtureRequest",
    "Item",
    "Mark",
    "MarkDecorator",
    "MonkeyPatch",
    "Session",
    "approx",
    "exit",
    "fail",
    "fixture",
    "hookimpl",
    "mark",
    "param",
    "raises",
    "skip",
]
