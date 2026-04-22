from collections.abc import Callable, Iterator

import pytest

from utils import wait_conditions


pytestmark = pytest.mark.scenario("TEST_THE_TEST")


@pytest.fixture(autouse=True)
def clear_wait_conditions() -> Iterator[None]:
    wait_conditions.clear()
    yield
    wait_conditions.clear()


class FakeResponse:
    def __init__(self, rid: str) -> None:
        self.rid = rid

    def get_rid(self) -> str:
        return self.rid


class FakeWeblog:
    def __init__(self) -> None:
        self.requests: list[str] = []

    def get(self, path: str = "/", **_kwargs: object) -> FakeResponse:
        self.requests.append(path)
        return FakeResponse(f"rid-{len(self.requests)}")


class FakeLibraryInterface:
    def __init__(self, *, captured: bool = False, capture_during_wait: bool = False) -> None:
        self.captured = captured
        self.capture_during_wait = capture_during_wait
        self.wait_for_calls: list[float] = []
        self.get_spans_calls = 0

    def get_spans(self, request: object | None = None, *, full_trace: bool = False) -> Iterator[object]:  # noqa: ARG002
        self.get_spans_calls += 1
        if self.captured and request is not None:
            yield object()

    def wait_for(self, wait_for_function: Callable[[dict[str, object]], bool], timeout: float) -> None:
        self.wait_for_calls.append(timeout)
        if self.capture_during_wait:
            self.captured = True
            wait_for_function({})


class FakeInterfaces:
    def __init__(self, library: FakeLibraryInterface) -> None:
        self.library = library


def test_tracer_watermark_succeeds_with_existing_trace() -> None:
    weblog = FakeWeblog()
    library = FakeLibraryInterface(captured=True)
    condition = wait_conditions.make_tracer_watermark(weblog=weblog, interfaces=FakeInterfaces(library))

    assert condition.wait(0) is True
    assert weblog.requests == ["/"]
    assert library.wait_for_calls == []


def test_tracer_watermark_waits_for_trace() -> None:
    weblog = FakeWeblog()
    library = FakeLibraryInterface(capture_during_wait=True)
    condition = wait_conditions.make_tracer_watermark(
        weblog=weblog,
        interfaces=FakeInterfaces(library),
        timeout=12,
    )

    assert condition.wait(12) is True
    assert weblog.requests == ["/"]
    assert library.wait_for_calls == [12]


def test_tracer_watermark_checks_once_without_timeout() -> None:
    weblog = FakeWeblog()
    library = FakeLibraryInterface()
    condition = wait_conditions.make_tracer_watermark(weblog=weblog, interfaces=FakeInterfaces(library))

    assert condition.wait(0) is False
    assert weblog.requests == ["/"]
    assert library.wait_for_calls == []
    assert library.get_spans_calls == 2


def test_global_wait_conditions_registry() -> None:
    condition = wait_conditions.Condition(wait=lambda _timeout: True, description="registered")

    wait_conditions.add(condition)

    assert list(wait_conditions.iter_conditions()) == [condition]


def test_wait_conditions_run_clamps_timeouts_and_checks_every_condition(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 100.0
    seen_timeouts = []

    def fake_time() -> float:
        return now

    def first_wait(timeout: float) -> bool:
        nonlocal now
        seen_timeouts.append(timeout)
        now = 115.0
        return False

    def second_wait(timeout: float) -> bool:
        seen_timeouts.append(timeout)
        return False

    monkeypatch.setattr(wait_conditions.time, "time", fake_time)

    first = wait_conditions.Condition(wait=first_wait, description="first", timeout=20)
    second = wait_conditions.Condition(wait=second_wait, description="second", timeout=20)
    wait_conditions.add(first)
    wait_conditions.add(second)

    assert wait_conditions.run(deadline=110.0) == [first, second]
    assert seen_timeouts == [10.0, 0.0]
