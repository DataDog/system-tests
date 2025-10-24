from collections.abc import Generator
import contextlib
from http import HTTPStatus
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import TextIO
import urllib.parse

from docker.models.containers import Container
import pytest
import requests

from utils._logger import logger

from ._core import docker_run, get_host_port


class TestClientFactory:
    """Abstracts a docker image. TODO: share this with parametric tests"""

    def __init__(
        self,
        dockerfile: str,
        build_args: dict[str, str],
        tag: str,
        container_name: str,
        container_volumes: dict[str, str],
        container_env: dict[str, str],
    ):
        self.dockerfile = dockerfile
        self.build_args = build_args
        self.tag = tag

        self.container_name = container_name
        self.container_volumes = container_volumes
        self.container_env: dict[str, str] = dict(container_env)

    def build(self, host_log_folder: str, github_token_file: str) -> None:
        log_path = f"{host_log_folder}/outputs/docker_build_log.log"
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
                pytest.exit(f"Failed to build framework test server image. See {log_path} for details", 1)


class FrameworkTestClientFactory(TestClientFactory):
    """Abstracts the docker image/container that ship the tested tracer+framework.
    This class is responsible to:
    * build the image
    * expose a ready to call function that runs the container and returns the client that will be used in tests
    """

    def __init__(
        self,
        library: str,
        framework: str,
        framework_version: str,
        container_env: dict[str, str],
        container_volumes: dict[str, str],
    ):
        self.library = library
        self.framework = framework
        self.framework_version = framework_version
        super().__init__(
            dockerfile=f"utils/build/docker/{library}/{framework}.Dockerfile",
            build_args={"FRAMEWORK_VERSION": framework_version},
            tag=f"{library}-test-library-{framework}-{framework_version}",
            container_name=f"{library}-test-library-{framework}-{framework_version}",
            container_volumes=container_volumes,
            container_env=container_env,
        )

    @contextlib.contextmanager
    def get_client(
        self,
        library_env: dict[str, str],
        worker_id: str,
        test_id: str,
        test_agent_container_name: str,
        test_agent_port: int,
        network: str,
        log_file: TextIO,
    ) -> Generator["FrameworkTestClient", None, None]:
        environment = dict(self.container_env)

        container_port: int = 8080
        host_port = get_host_port(worker_id, 4500)

        # TODO : we should not have to set those three values
        environment["DD_TRACE_AGENT_URL"] = f"http://{test_agent_container_name}:{test_agent_port}"
        environment["DD_AGENT_HOST"] = test_agent_container_name
        environment["DD_TRACE_AGENT_PORT"] = str(test_agent_port)
        environment["FRAMEWORK_TEST_CLIENT_SERVER_PORT"] = str(container_port)

        # overwrite env with the one provided by the test
        environment |= library_env

        with docker_run(
            image=self.tag,
            name=f"{self.container_name}-{test_id}",
            env=environment,
            volumes=self.container_volumes,
            network=network,
            ports={f"{container_port}/tcp": host_port},
            log_file=log_file,
        ) as container:
            test_server_timeout = 60
            client = FrameworkTestClient(f"http://localhost:{host_port}", test_server_timeout, container)

            yield client


class FrameworkTestClient:
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
                    pytest.fail(message)
            time.sleep(delay)
        else:
            self._print_logs()
            message = f"Timeout of {timeout} seconds exceeded waiting for HTTP server to start. Please check logs."
            pytest.fail(message)

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
