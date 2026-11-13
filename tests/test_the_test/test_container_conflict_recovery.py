from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from docker.errors import APIError
import requests

from utils import scenarios, pytest
from utils._context.containers import TestedContainer as _TestedContainer


def _api_error(status: HTTPStatus) -> APIError:
    response = requests.Response()
    response.status_code = status
    return APIError(status.phrase, response=response, explanation=status.phrase)


@contextmanager
def _started(container: _TestedContainer, client: MagicMock) -> Iterator[MagicMock]:
    with (
        patch("utils._context.containers.get_docker_client", return_value=client),
        patch("utils._context.containers.log_host_diagnostics") as log_host_diagnostics,
        patch("utils._context.containers._CONFLICT_RETRY_DELAY", 0),
        patch.object(container, "get_existing_container", return_value=None),
        patch.object(container, "wait_for_health", return_value=False),
    ):
        yield log_host_diagnostics


@scenarios.test_the_test
def test_leftover_container_is_replaced() -> None:
    container = _TestedContainer(name="conflict-test", image_name="unused")
    client = MagicMock()
    started = MagicMock()
    client.containers.run.side_effect = [_api_error(HTTPStatus.CONFLICT), started]

    with _started(container, client) as log_host_diagnostics:
        container.start(MagicMock())

    client.api.remove_container.assert_called_once_with("system-tests-conflict-test", force=True)
    assert client.containers.run.call_count == 2
    assert container._container is started  # noqa: SLF001
    log_host_diagnostics.assert_not_called()


@scenarios.test_the_test
# 404: the daemon is still creating it. 409: its removal is already in progress.
@pytest.mark.parametrize("removal_status", [HTTPStatus.NOT_FOUND, HTTPStatus.CONFLICT])
def test_leftover_container_not_yet_removable_is_retried(removal_status: HTTPStatus) -> None:
    container = _TestedContainer(name="conflict-test", image_name="unused")
    client = MagicMock()
    client.containers.run.side_effect = [_api_error(HTTPStatus.CONFLICT), _api_error(HTTPStatus.CONFLICT), MagicMock()]
    client.api.remove_container.side_effect = [_api_error(removal_status), None]

    with _started(container, client):
        container.start(MagicMock())

    assert client.api.remove_container.call_count == 2
    assert client.containers.run.call_count == 3


@scenarios.test_the_test
def test_unexpected_removal_failure_is_raised() -> None:
    container = _TestedContainer(name="conflict-test", image_name="unused")
    client = MagicMock()
    client.containers.run.side_effect = [_api_error(HTTPStatus.CONFLICT), MagicMock()]
    client.api.remove_container.side_effect = _api_error(HTTPStatus.INTERNAL_SERVER_ERROR)

    with _started(container, client), pytest.raises(APIError) as exc_info:
        container.start(MagicMock())

    assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert client.containers.run.call_count == 1


@scenarios.test_the_test
def test_conflict_recovery_stops_at_the_deadline() -> None:
    container = _TestedContainer(name="conflict-test", image_name="unused")
    client = MagicMock()
    client.containers.run.side_effect = _api_error(HTTPStatus.CONFLICT)

    with (
        _started(container, client),
        # the deadline is already over when the recovery starts
        patch("utils._context.containers._CONFLICT_RECOVERY_SECONDS", -1),
        pytest.raises(APIError) as exc_info,
    ):
        container.start(MagicMock())

    assert exc_info.value.status_code == HTTPStatus.CONFLICT
    # the first attempt, then a single recovery attempt: no attempt starts after the deadline
    assert client.containers.run.call_count == 2


@scenarios.test_the_test
def test_host_diagnostics_are_logged_on_timeouts_only() -> None:
    container = _TestedContainer(name="timeout-test", image_name="unused")
    client = MagicMock()
    client.containers.run.side_effect = requests.exceptions.ReadTimeout()

    with _started(container, client) as log_host_diagnostics, pytest.raises(requests.exceptions.ReadTimeout):
        container.start(MagicMock())
    log_host_diagnostics.assert_called_once()

    client.containers.run.side_effect = _api_error(HTTPStatus.INTERNAL_SERVER_ERROR)
    with _started(container, client) as log_host_diagnostics, pytest.raises(APIError):
        container.start(MagicMock())
    log_host_diagnostics.assert_not_called()
