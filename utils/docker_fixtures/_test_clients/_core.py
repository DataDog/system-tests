import os
import re
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

from utils._context._image_mirror import mirror_enabled
from utils._logger import logger
from utils.base_images.base_image import base_image_contexts
from utils.docker_fixtures._core import get_docker_client


def _fail(message: str):
    """Used to mak a test as failed"""
    logger.error(message)
    raise Failed(message, pytrace=False) from None


_MIRROR_BUILDER = "system-tests-mirror"
_BUILDKITD_CONFIG = "utils/build/docker/buildkitd.toml"


def _ensure_mirror_builder(docker_bin: str) -> str:
    """Create (or reuse) the buildx builder configured to pull through the image mirror."""
    inspect = subprocess.run([docker_bin, "buildx", "inspect", _MIRROR_BUILDER], capture_output=True, check=False)
    if inspect.returncode != 0:
        subprocess.run(
            [docker_bin, "buildx", "create", "--name", _MIRROR_BUILDER, "--config", _BUILDKITD_CONFIG],
            check=True,
        )
    return _MIRROR_BUILDER


# Registry / network errors that are worth retrying the build for. The base images are
# passed as docker-image:// build contexts, so a flaky registry (HEAD/GET on the manifest
# or a blob) fails the build before any Dockerfile instruction is executed.
_TRANSIENT_BUILD_ERROR = re.compile(
    r"TLS handshake timeout"
    r"|i/o timeout"
    r"|connection reset by peer"
    r"|connection refused"
    r"|net/http: request canceled"  # "while waiting for connection", "(Client.Timeout exceeded ...)"
    r"|context deadline exceeded"
    r"|temporary failure in name resolution"
    r"|no such host"
    r"|unexpected EOF"
    r"|: EOF$"  # connection closed during a request (e.g. Head "...": EOF)
    r"|code = Unavailable"  # buildx lost its builder (rpc error ... error reading from server: EOF)
    r"|toomanyrequests"
    r"|429 Too Many Requests"
    r"|\b50[0234] (?:Internal Server Error|Bad Gateway|Service Unavailable|Gateway Timeout)\b",
    re.IGNORECASE,
)
# Only the lines that describe why the build failed are classified: buildx's final summary
# (column 0, e.g. "ERROR: failed to solve: ...") and the failing step ("#5 ERROR: ...").
# Step output is always prefixed with "#N <time>", so an error printed (and maybe recovered
# from) by a step never matches.
_BUILD_FAILURE_LINE = re.compile(r"^(?:#\d+ )?ERROR: ")
# A RUN instruction that exits non-zero, or an invalid Dockerfile, is a real build failure,
# even if the message mentions a network error (or ends with ": EOF"): never retry it.
_NON_TRANSIENT_FAILURES = ("did not complete successfully", "dockerfile parse error")
_BUILD_ATTEMPTS = 3
_BUILD_RETRY_DELAYS = (10, 30)  # seconds to wait before attempt 2, 3
_BUILD_ATTEMPT_TIMEOUT = 600  # seconds, for one attempt
_BUILD_TOTAL_TIMEOUT = 900  # seconds, for all attempts and waits
_BUILD_MIN_ATTEMPT_BUDGET = 120  # seconds: don't start an attempt with less time than this left


def _is_transient_build_failure(output: str) -> bool:
    """Tell whether a failed docker build log only shows a transient registry/network error"""
    failure_lines = [line.rstrip() for line in output.splitlines() if _BUILD_FAILURE_LINE.match(line)]
    if any(marker in line for line in failure_lines for marker in _NON_TRANSIENT_FAILURES):
        return False
    return any(_TRANSIENT_BUILD_ERROR.search(line) for line in failure_lines)


def _append_to_log(log_path: str, message: str) -> None:
    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(f"\n===== {message} =====\n")


def _run_docker_build(
    cmd: list[str],
    log_path: str,
    env: dict[str, str],
    attempt_timeout: float = _BUILD_ATTEMPT_TIMEOUT,
    total_timeout: float = _BUILD_TOTAL_TIMEOUT,
) -> int:
    """Run the docker build, retrying on transient registry/network errors.

    Each attempt is limited to attempt_timeout, and all attempts (with the waits between them)
    to total_timeout. A timeout raises subprocess.TimeoutExpired, it is not retried.
    Every attempt is appended to log_path, after an attempt header.
    Returns the exit code of the last attempt.
    """
    deadline = time.monotonic() + total_timeout
    returncode = 0
    for attempt in range(1, _BUILD_ATTEMPTS + 1):
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n===== docker build attempt {attempt}/{_BUILD_ATTEMPTS} =====\n")
            log_file.flush()
            attempt_start = os.fstat(log_file.fileno()).st_size

            returncode = subprocess.run(
                cmd,
                text=True,
                stdout=log_file,
                stderr=log_file,
                env=env,
                timeout=min(attempt_timeout, deadline - time.monotonic()),
                check=False,
            ).returncode

        if returncode == 0:
            return 0

        attempt_output = Path(log_path).read_bytes()[attempt_start:].decode(errors="replace")

        if attempt == _BUILD_ATTEMPTS or not _is_transient_build_failure(attempt_output):
            return returncode

        delay = _BUILD_RETRY_DELAYS[min(attempt, len(_BUILD_RETRY_DELAYS)) - 1]
        if deadline - time.monotonic() - delay < _BUILD_MIN_ATTEMPT_BUDGET:
            message = (
                f"docker build attempt {attempt}/{_BUILD_ATTEMPTS} failed with a transient registry/network error, "
                f"not retrying: less than {_BUILD_MIN_ATTEMPT_BUDGET}s left of the {total_timeout:.0f}s build budget"
            )
            logger.stdout(message)
            _append_to_log(log_path, message)
            return returncode

        message = (
            f"docker build attempt {attempt}/{_BUILD_ATTEMPTS} failed with a transient registry/network error, "
            f"retrying in {delay}s"
        )
        logger.stdout(message)
        _append_to_log(log_path, message)
        time.sleep(delay)

    return returncode


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

        with open(log_path, "w", encoding="utf-8") as log_file:
            docker_bin = shutil.which("docker")

            if docker_bin is None:
                raise FileNotFoundError("Docker not found in PATH")

            if mirror_enabled():
                # Same builder as weblog builds (utils/build/build.sh): its buildkitd
                # daemon redirects all FROM pulls through the system-tests mirror.
                # It does not use the docker driver, so the image must be loaded back.
                # Equivalent to --load, but skips layer compression: the tarball is only
                # streamed to the local docker daemon, so gzip just burns CPU time.
                cmd = [
                    docker_bin,
                    "buildx",
                    "build",
                    "--builder",
                    _ensure_mirror_builder(docker_bin),
                    "--output",
                    "type=docker,compression=uncompressed",
                ]
            else:
                cmd = [docker_bin, "build"]
            cmd += ["--progress=plain"]

            if github_token_file and github_token_file.strip():
                cmd += ["--secret", f"id=github_token,src={github_token_file}"]

            for name, value in self.build_args.items():
                cmd += ["--build-arg", f"{name}={value}"]

            for alias, image in base_image_contexts(Path(self.dockerfile).read_text()).items():
                cmd += ["--build-context", f"{alias}=docker-image://{image}"]

            cmd += [
                "-t",
                self.tag,
                "-f",
                self.dockerfile,
                ".",
            ]
            log_file.write(f"running {cmd}\n")

        env = os.environ.copy()
        env["DOCKER_SCAN_SUGGEST"] = "false"

        if _run_docker_build(cmd, log_path, env) != 0:
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
        logger.debug(f"Waiting for {self.container.name} being ready")
        for _ in range(int(timeout / delay)):
            try:
                if self._is_alive():
                    logger.debug(f"{self.container.name} is ready")
                    break
            except Exception:
                # don't log anything here, it makes the ouput very noisy
                ...

            # _is_alive() swallows a non-running container status and returns False instead of
            # raising, so the check must be repeated here on every iteration (not only in the
            # except branch above) or a container that exits early (e.g. crash, port collision)
            # silently gets retried for the full timeout instead of failing fast with its logs.
            self.container.reload()
            if self.container.status not in ("running", "created"):
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
