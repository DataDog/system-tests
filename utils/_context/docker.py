from datetime import datetime, UTC
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
from threading import Lock

import docker
from docker.errors import DockerException
import pytest
from requests.exceptions import RequestException

from utils._logger import logger

# docker-py's default is 60s. On ubuntu-26.04 GitHub runners (Docker 29, containerd image store), the first
# containers/create of a job sometimes stalls for ~60s before completing: give the daemon time to answer.
DOCKER_CLIENT_TIMEOUT = 180


@lru_cache
def get_docker_client() -> docker.DockerClient:
    try:
        return docker.DockerClient.from_env(timeout=DOCKER_CLIENT_TIMEOUT)
    except DockerException as e:
        # Failed to start the default Docker client... Let's see if we have
        # better luck with docker contexts...
        try:
            ctx_name = subprocess.run(
                ["docker", "context", "show"], capture_output=True, check=True, text=True
            ).stdout.strip()
            endpoint = subprocess.run(
                ["docker", "context", "inspect", ctx_name, "-f", "{{ .Endpoints.docker.Host }}"],
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
            return docker.DockerClient(base_url=endpoint, timeout=DOCKER_CLIENT_TIMEOUT)
        except (subprocess.CalledProcessError, DockerException, RequestException, ValueError):
            logger.exception("No more success with docker contexts")

        if "Error while fetching server API version: ('Connection aborted.'" in str(e):
            pytest.exit("Connection refused to docker daemon, is it running?", 1)

        raise


# (command, keep the last lines instead of the first ones)
_HOST_DIAGNOSTIC_COMMANDS: list[tuple[list[str], bool]] = [
    (["uptime"], False),
    (["free", "-m"], False),
    (["df", "-h", "/"], False),
    # pressure stall information: share of time tasks waited on CPU, I/O or memory
    (["grep", "-H", ".", "/proc/pressure/cpu", "/proc/pressure/io", "/proc/pressure/memory"], False),
    # the wa column is the I/O wait
    (["vmstat", "1", "3"], False),
    (["ps", "aux", "--sort=-%mem"], False),
    # processes in uninterruptible sleep (usually waiting on I/O), and the kernel function they wait in
    (["sh", "-c", "ps -eo stat,pid,etime,wchan:32,args | awk 'NR == 1 || $1 ~ /D/'"], False),
    (["sudo", "-n", "dmesg", "-T"], True),
    (["sudo", "-n", "journalctl", "-u", "docker.service", "-u", "containerd.service", "--since", "-5min"], True),
    (["docker", "ps", "-a"], False),
]

# SIGUSR1 makes dockerd write its goroutine stacks to a file in its run dir, and containerd log its stacks
_DAEMON_STACKS_SCRIPT = """
marker=$(mktemp)
dockerd_pid=$(pidof dockerd) && kill -USR1 "$dockerd_pid"
containerd_pid=$(pidof containerd) && kill -USR1 "$containerd_pid"
sleep 2
echo "### dockerd"
find /var/run/docker -maxdepth 1 -name 'goroutine-stacks-*.log' -newer "$marker" -exec cat {} +
echo "### containerd"
journalctl -u containerd.service --since -1min --no-pager -o cat
rm -f "$marker"
"""

_diagnostics_lock = Lock()


def log_host_diagnostics(reason: str, daemon_stacks_folder: str | None = None) -> None:
    """Log the host state when the docker daemon is slow, to tell memory/CPU/IO starvation from a daemon issue.

    If daemon_stacks_folder is set, also dump the goroutine stacks of dockerd and containerd in this folder, to see
    what the daemon is waiting on. Call it while the daemon is still stuck.
    """

    # containers start in parallel threads: don't interleave their diagnostics
    with _diagnostics_lock:
        logger.warning(f"Host diagnostics ({reason}):")

        if daemon_stacks_folder is not None and sys.platform == "linux":
            _dump_daemon_stacks(Path(daemon_stacks_folder))

        for command, keep_last in _HOST_DIAGNOSTIC_COMMANDS:
            output = _run(command)
            lines = output[-40:] if keep_last else output[:40]
            logger.warning(f"$ {' '.join(command)}\n" + "\n".join(lines))


def _dump_daemon_stacks(folder: Path) -> None:
    path = folder / f"daemon-stacks-{datetime.now(UTC):%H%M%S}.log"
    output = _run(["sudo", "-n", "sh", "-c", _DAEMON_STACKS_SCRIPT])
    try:
        path.write_text("\n".join(output) + "\n", encoding="utf-8")
    except OSError as e:
        logger.warning(f"Can't write the daemon stacks to {path}: {e}")
    else:
        logger.warning(f"Daemon stacks written to {path}")


def _run(command: list[str]) -> list[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [f"failed: {e}"]

    return (result.stdout + result.stderr).splitlines()
