import io

from _pytest.outcomes import Failed
from docker.errors import APIError, NotFound
import pytest

from utils import scenarios
from utils.docker_fixtures._core import INVOCATION_LABEL, docker_run, new_test_id


class _FakeContainer:
    def __init__(
        self,
        *,
        name: str = "test-client-deadbeef",
        labels: dict[str, str] | None = None,
        stop_exc: Exception | None = None,
        logs_exc: Exception | None = None,
        remove_exc: Exception | None = None,
    ) -> None:
        self.name = name
        self.labels = labels or {}
        self._stop_exc = stop_exc
        self._logs_exc = logs_exc
        self._remove_exc = remove_exc
        self.removed = 0

    def stop(self, timeout: int) -> None:  # noqa: ARG002
        if self._stop_exc is not None:
            raise self._stop_exc

    def logs(self) -> bytes:
        if self._logs_exc is not None:
            raise self._logs_exc
        return b"hello from client\n"

    def remove(self, *, force: bool) -> None:
        assert force is True
        self.removed += 1
        if self._remove_exc is not None:
            raise self._remove_exc


class _FakeClient:
    def __init__(
        self,
        *,
        container: _FakeContainer | None = None,
        run_exc: Exception | None = None,
        existing: list[_FakeContainer] | None = None,
        creates_before_failing: bool = False,
    ) -> None:
        self.containers = self
        self.existing = list(existing or [])
        self._container = container
        self._run_exc = run_exc
        self._creates_before_failing = creates_before_failing

    def run(
        self,
        image: str,  # noqa: ARG002
        *,
        name: str,
        labels: dict[str, str],
        **_rest: object,
    ) -> _FakeContainer | None:
        if self._run_exc is not None:
            if self._creates_before_failing:
                self.existing.append(_FakeContainer(name=name, labels=dict(labels)))
            raise self._run_exc
        return self._container

    def list(self, *, filters: dict[str, str], **_rest: object) -> list[_FakeContainer]:
        label = filters.get("label")
        assert label is not None, "cleanup must select by ownership label, never by container name"
        key, _, value = label.partition("=")
        return [c for c in self.existing if c.labels.get(key) == value]


def _docker_run(client: _FakeClient, log_file: io.StringIO):
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("utils.docker_fixtures._core.get_docker_client", lambda: client)
    return docker_run(
        image="image",
        name="test-client-deadbeef",
        env={},
        volumes={},
        network="net",
        ports={},
        log_file=log_file,
    )


def _run(client: _FakeClient) -> io.StringIO:
    log_file = io.StringIO()
    with _docker_run(client, log_file):
        pass
    return log_file


@scenarios.test_the_test
def test_test_id_is_wide_enough_not_to_collide():
    assert len(new_test_id()) == 16
    assert len({new_test_id() for _ in range(10_000)}) == 10_000


@scenarios.test_the_test
def test_container_logs_are_captured_and_container_removed():
    container = _FakeContainer()

    log_file = _run(_FakeClient(container=container))

    assert log_file.getvalue() == "hello from client\n"
    assert container.removed == 1


@scenarios.test_the_test
@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"logs_exc": APIError("409 dead or marked for removal")}, id="logs_fails"),
        pytest.param({"stop_exc": APIError("stop failed")}, id="stop_fails"),
    ],
)
def test_teardown_failure_still_removes_container_and_still_fails_loudly(kwargs: dict):
    container = _FakeContainer(**kwargs)

    with pytest.raises(APIError):
        _run(_FakeClient(container=container))

    assert container.removed == 1


@scenarios.test_the_test
def test_already_removed_container_does_not_fail_teardown():
    container = _FakeContainer(remove_exc=NotFound("already gone"))

    _run(_FakeClient(container=container))

    assert container.removed == 1


@scenarios.test_the_test
def test_body_exception_propagates_and_container_is_removed():
    container = _FakeContainer()

    with pytest.raises(ValueError, match="boom"), _docker_run(_FakeClient(container=container), io.StringIO()):
        raise ValueError("boom")

    assert container.removed == 1


@scenarios.test_the_test
def test_failed_create_does_not_remove_another_workers_container():
    foreign = _FakeContainer(labels={INVOCATION_LABEL: "another-invocation"})
    client = _FakeClient(run_exc=APIError("409 name is already in use"), existing=[foreign])

    with pytest.raises(Failed):
        _run(client)

    assert foreign.removed == 0


@scenarios.test_the_test
def test_failed_create_removes_only_the_container_it_created():
    client = _FakeClient(run_exc=APIError("start failed"), creates_before_failing=True)

    with pytest.raises(Failed):
        _run(client)

    assert [c.removed for c in client.existing] == [1]
