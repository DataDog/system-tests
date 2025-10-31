import os
from pathlib import Path
import shutil
import subprocess

from docker.models.images import Image
import pytest

from utils._logger import logger

from ._core import get_docker_client


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
