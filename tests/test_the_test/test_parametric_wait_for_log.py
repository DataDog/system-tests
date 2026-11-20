from typing import TYPE_CHECKING, cast

from tests.parametric.conftest import APMLibrary, nodejs_startup_config
from utils import pytest, scenarios

if TYPE_CHECKING:
    from docker.models.containers import Container


class _FakeContainer:
    def __init__(self, *outputs: str) -> None:
        self._outputs = list(outputs)
        self.calls = 0

    def logs(self) -> bytes:
        self.calls += 1
        return self._outputs[min(self.calls, len(self._outputs)) - 1].encode()


def _library(container: _FakeContainer) -> APMLibrary:
    library = APMLibrary.__new__(APMLibrary)
    library.container = cast("Container", container)
    return library


@scenarios.test_the_test
def test_wait_for_log_polls_until_marker() -> None:
    container = _FakeContainer("", "starting\n", "starting\nMARKER\n", "never read")
    assert _library(container).wait_for_log("MARKER", interval=0) == "starting\nMARKER\n"
    assert container.calls == 3


@scenarios.test_the_test
def test_wait_for_log_accepts_predicate() -> None:
    container = _FakeContainer("a", "ab", "abc")
    assert _library(container).wait_for_log(lambda logs: len(logs) == 3, interval=0) == "abc"
    assert container.calls == 3


@scenarios.test_the_test
def test_wait_for_log_returns_last_logs_on_timeout() -> None:
    container = _FakeContainer("first", "last")
    assert _library(container).wait_for_log("MARKER", timeout=0.05, interval=0.01) == "last"
    assert container.calls >= 2


@scenarios.test_the_test
def test_nodejs_startup_config_waits_for_late_line() -> None:
    line = 'DATADOG TRACER CONFIGURATION - {"agent_url": "unix:///nonexistent"}'
    container = _FakeContainer("", "", f"{line}\n")
    assert nodejs_startup_config(_library(container)) == {"agent_url": "unix:///nonexistent"}
    assert container.calls == 3


@scenarios.test_the_test
def test_nodejs_startup_config_fails_without_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(APMLibrary, "wait_for_log", lambda self, _match: self.get_logs())
    with pytest.raises(AssertionError, match="No 'DATADOG TRACER CONFIGURATION' line"):
        nodejs_startup_config(_library(_FakeContainer("no startup line")))
