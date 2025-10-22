from docker.models.containers import Container
import requests

from _pytest.outcomes import Failed
from utils._logger import logger
import time
from http import HTTPStatus
import urllib.parse

def _fail(message: str):
    """Used to mak a test as failed"""
    logger.error(message)
    raise Failed(message, pytrace=False) from None

class FrameworkLibraryClient:
    def __init__(self, url: str, timeout: int, container: Container):
        self._base_url = url
        self._session = requests.Session()
        self.container = container
        self.timeout = timeout

        # wait for server to start
        self._wait(timeout)

    def container_restart(self):
        self.container.restart()
        self._wait(self.timeout)

    def _wait(self, timeout: float):
        delay = 0.01
        for _ in range(int(timeout / delay)):
            try:
                if self.is_alive():
                    break
            except Exception:
                if self.container.status != "running":
                    self._print_logs()
                    message = f"Container {self.container.name} status is {self.container.status}. Please check logs."
                    _fail(message)
            time.sleep(delay)
        else:
            self._print_logs()
            message = f"Timeout of {timeout} seconds exceeded waiting for HTTP server to start. Please check logs."
            _fail(message)

    def is_alive(self) -> bool:
        self.container.reload()
        return (
            self.container.status == "running"
            and self._session.get(self._url("/non-existent-endpoint-to-ping-until-the-server-starts")).status_code
            == HTTPStatus.NOT_FOUND
        )

    def request(self, method: str, url: str, body: dict | None = None) -> requests.Response:
        resp = self._session.request(method, self._url(url), json=body)
        resp.raise_for_status()
        return resp

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def _print_logs(self):
        try:
            logs = self.container.logs().decode("utf-8")
            logger.debug(f"Logs from container {self.container.name}:\n\n{logs}")
        except Exception:
            logger.error(f"Failed to get logs from container {self.container.name}")

class FrameworkClient:
    def __init__(self, client: FrameworkLibraryClient, lang: str):
        self._client = client
        self.lang = lang

    def request(self, method: str, url: str, body: dict | None = None) -> requests.Response:
        return self._client.request(method, url, body)
