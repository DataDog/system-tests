import contextlib
from collections.abc import Iterator
import io

from _pytest.outcomes import Failed
from docker.errors import APIError, NotFound
from utils import pytest

from utils import scenarios
from utils.docker_fixtures import _core as docker_core
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

    def stop(self, timeout: int) -> None:
        del timeout
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
        create_remove_excs: list[Exception | None] | None = None,
        list_exc: Exception | None = None,
    ) -> None:
        self.containers = self
        self.existing = list(existing or [])
        self._container = container
        self._run_exc = run_exc
        self._create_remove_excs = create_remove_excs or []
        self._list_exc = list_exc

    def run(
        self,
        _image: str,
        *,
        name: str,
        labels: dict[str, str],
        **_rest: object,
    ) -> _FakeContainer | None:
        if self._run_exc is not None:
            self.existing.extend(
                _FakeContainer(name=name, labels=dict(labels), remove_exc=remove_exc)
                for remove_exc in self._create_remove_excs
            )
            raise self._run_exc
        return self._container

    def list(self, *, filters: dict[str, str], **_rest: object) -> list[_FakeContainer]:
        if self._list_exc is not None:
            raise self._list_exc
        label = filters.get("label")
        assert label is not None, "cleanup must select by ownership label, never by container name"
        key, _, value = label.partition("=")
        return [c for c in self.existing if c.labels.get(key) == value]


@contextlib.contextmanager
def _docker_run(client: _FakeClient, log_file: io.StringIO) -> Iterator[None]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("utils.docker_fixtures._core.get_docker_client", lambda: client)
        with docker_run(
            image="image",
            name="test-client-deadbeef",
            env={},
            volumes={},
            network="net",
            ports={},
            log_file=log_file,
        ):
            yield


def _run(client: _FakeClient) -> io.StringIO:
    log_file = io.StringIO()
    with _docker_run(client, log_file):
        pass
    return log_file


@scenarios.test_the_test
def test_test_id_uses_64_random_bits(monkeypatch: pytest.MonkeyPatch):
    calls: list[int] = []

    def token_hex(byte_count: int) -> str:
        calls.append(byte_count)
        return "00abcdef12345678"

    monkeypatch.setattr(docker_core.secrets, "token_hex", token_hex)

    assert new_test_id() == "00abcdef12345678"
    assert calls == [8]


@scenarios.test_the_test
def test_container_logs_are_captured_and_container_removed():
    container = _FakeContainer()

    log_file = _run(_FakeClient(container=container))

    assert log_file.getvalue() == "hello from client\n"
    assert container.removed == 1


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("stop_exc", "logs_exc"),
    [
        pytest.param(None, APIError("409 dead or marked for removal"), id="logs_fails"),
        pytest.param(APIError("stop failed"), None, id="stop_fails"),
    ],
)
def test_teardown_failure_still_removes_container_and_still_fails_loudly(
    stop_exc: Exception | None, logs_exc: Exception | None
):
    container = _FakeContainer(stop_exc=stop_exc, logs_exc=logs_exc)

    with pytest.raises(APIError):
        _run(_FakeClient(container=container))

    assert container.removed == 1


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("stop_exc", "logs_exc"),
    [
        pytest.param(None, APIError("logs failed"), id="logs_fails"),
        pytest.param(APIError("stop failed"), None, id="stop_fails"),
    ],
)
def test_teardown_failure_is_preserved_when_removal_also_fails(stop_exc: Exception | None, logs_exc: Exception | None):
    teardown_error = stop_exc or logs_exc
    assert teardown_error is not None
    remove_error = APIError("remove failed")
    container = _FakeContainer(stop_exc=stop_exc, logs_exc=logs_exc, remove_exc=remove_error)

    with pytest.raises(APIError) as exc_info:
        _run(_FakeClient(container=container))

    assert exc_info.value is teardown_error
    assert container.removed == 1


@scenarios.test_the_test
def test_already_removed_container_does_not_fail_teardown():
    container = _FakeContainer(remove_exc=NotFound("already gone"))

    _run(_FakeClient(container=container))

    assert container.removed == 1


@scenarios.test_the_test
def test_removal_failure_propagates_when_no_other_error_exists():
    remove_error = APIError("remove failed")
    container = _FakeContainer(remove_exc=remove_error)

    with pytest.raises(APIError) as exc_info:
        _run(_FakeClient(container=container))

    assert exc_info.value is remove_error
    assert container.removed == 1


@scenarios.test_the_test
def test_body_exception_propagates_and_container_is_removed():
    container = _FakeContainer()

    with pytest.raises(ValueError, match="boom"), _docker_run(_FakeClient(container=container), io.StringIO()):
        raise ValueError("boom")

    assert container.removed == 1


@scenarios.test_the_test
def test_body_exception_is_preserved_when_removal_also_fails():
    container = _FakeContainer(remove_exc=APIError("remove failed"))

    with pytest.raises(ValueError, match="boom"), _docker_run(_FakeClient(container=container), io.StringIO()):
        raise ValueError("boom")

    assert container.removed == 1


@scenarios.test_the_test
def test_docker_client_patch_is_restored_after_helper_invocation():
    original = docker_core.get_docker_client

    _run(_FakeClient(container=_FakeContainer()))

    assert docker_core.get_docker_client is original


@scenarios.test_the_test
def test_failed_create_does_not_remove_another_workers_container():
    foreign = _FakeContainer(labels={INVOCATION_LABEL: "another-invocation"})
    client = _FakeClient(run_exc=APIError("409 name is already in use"), existing=[foreign])

    with pytest.raises(Failed):
        _run(client)

    assert foreign.removed == 0


@scenarios.test_the_test
def test_failed_create_removes_only_the_container_it_created():
    client = _FakeClient(run_exc=APIError("start failed"), create_remove_excs=[None])

    with pytest.raises(Failed):
        _run(client)

    assert [c.removed for c in client.existing] == [1]


@scenarios.test_the_test
def test_failed_create_preserves_run_error_when_listing_for_cleanup_fails():
    client = _FakeClient(run_exc=APIError("start failed"), list_exc=APIError("list failed"))

    with pytest.raises(Failed, match=r"start failed.*list failed"):
        _run(client)


@scenarios.test_the_test
def test_failed_create_attempts_all_removals_and_reports_cleanup_errors():
    client = _FakeClient(
        run_exc=APIError("start failed"),
        create_remove_excs=[NotFound("already gone"), APIError("remove failed"), None],
    )

    with pytest.raises(Failed, match=r"start failed.*remove failed"):
        _run(client)

    assert [c.removed for c in client.existing] == [1, 1, 1]
