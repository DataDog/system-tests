import os
import shutil
import subprocess
import time
import urllib.parse
from http import HTTPStatus
from pathlib import Path
from typing import TextIO

from docker.models.images import Image
from docker.models.containers import Container
import pytest
import requests
from _pytest.outcomes import Failed

from utils._logger import logger
from utils.docker_fixtures._core import get_docker_client


def _fail(message: str):
    """Used to mak a test as failed"""
    logger.error(message)
    raise Failed(message, pytrace=False) from None


class TestClientFactory:
    """Abstracts a docker image builing for docker fixtures scenarios"""

    _image: Image | None
    host_log_folder: str

    def __init__(
        self,
        library: str,
        dockerfile: str,
        tag: str,
        container_name: str,
        container_volumes: dict[str, str],
        container_env: dict[str, str],
        build_args: dict[str, str] | None = None,
    ):
        self.library = library
        self.dockerfile = dockerfile
        self.build_args: dict[str, str] = build_args or {}
        self.tag = tag

        self.container_name = container_name
        self.container_volumes = container_volumes
        self.container_env: dict[str, str] = dict(container_env)
        self._image = None

    def configure(self, host_log_folder: str):
        self.host_log_folder = host_log_folder

    def build(self, github_token_file: str) -> None:
        logger.stdout("Build framework test container...")
        log_path = f"{self.host_log_folder}/outputs/docker_build_log.log"
        Path.mkdir(Path(log_path).parent, exist_ok=True, parents=True)

        with open(log_path, "w+", encoding="utf-8") as log_file:
            docker_bin = shutil.which("docker")

            if docker_bin is None:
                raise FileNotFoundError("Docker not found in PATH")

            cmd = [
                docker_bin,
                "build",
                "--progress=plain",
            ]

            if github_token_file and github_token_file.strip():
                cmd += ["--secret", f"id=github_token,src={github_token_file}"]

            for name, value in self.build_args.items():
                cmd += ["--build-arg", f"{name}={value}"]

            cmd += [
                "-t",
                self.tag,
                "-f",
                self.dockerfile,
                ".",
            ]
            log_file.write(f"running {cmd}\n")
            log_file.flush()

            env = os.environ.copy()
            env["DOCKER_SCAN_SUGGEST"] = "false"

            timeout = 600

            p = subprocess.run(
                cmd,
                text=True,
                stdout=log_file,
                stderr=log_file,
                env=env,
                timeout=timeout,
                check=False,
            )

            if p.returncode != 0:
                with Path(log_path).open() as f:
                    lines = f.readlines()

                TAIL_LIMIT = 50  # noqa: N806
                SEP = "=" * 30  # noqa: N806

                logger.stdout(f"\n{SEP} {log_path} last {TAIL_LIMIT} lines {SEP}")
                logger.stdout("")
                # print last <tail> lines in stdout
                logger.stdout("".join(lines[-TAIL_LIMIT:]))
                logger.stdout("")

                pytest.exit(f"Failed to build framework test server image. See {log_path} for details", 1)

            # Sanity checks
            if "Config" not in self.image.attrs or not self.image.attrs["Config"].get("Cmd"):
                pytest.exit(f"{self.dockerfile} does not set a command", 1)

            assert isinstance(self.command, list)

        logger.stdout("Build complete")

    @property
    def image(self) -> Image:
        # as it may be called in a xdist, memoize it
        if self._image is None:
            self._image = get_docker_client().images.get(self.tag)

        return self._image

    @property
    def command(self) -> list[str]:
        return self.image.attrs["Config"]["Cmd"]

    def get_client_log_file(self, request: pytest.FixtureRequest) -> TextIO:
        log_path = Path(f"{self.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/server_log.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        return log_path.open("w+", encoding="utf-8")


class TestClientApi:
    """Base Test Client class for parametric and integration_framework scenario"""

    container: Container
    timeout: int
    _session: requests.Session
    _base_url: str

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
                if self._is_alive():
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

    def _url(self, path: str) -> str:
        return urllib.parse.urljoin(self._base_url, path)

    def _is_alive(self) -> bool:
        self.container.reload()

        if self.container.status != "running":
            logger.info(f"Container status is {self.container.status}, waiting...")
            return False

        status = self._session.get(self._url("/non-existent-endpoint-to-ping-until-the-server-starts")).status_code
        if status != HTTPStatus.NOT_FOUND:
            logger.info(f"HTTP app is not yet ready, status code is {status}, waiting...")
            return False

        return True

    def _print_logs(self):
        try:
            logs = self.container.logs().decode("utf-8")
            logger.debug(f"Logs from container {self.container.name}:\n\n{logs}")
        except Exception:
            logger.error(f"Failed to get logs from container {self.container.name}")
