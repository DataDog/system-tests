from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING, TextIO, cast
from urllib.error import URLError
from urllib.request import urlopen

from rebuildr import Build, BuildArg, File, ImageHandle, Project

from utils._context.docker import get_docker_client
from utils.docker_ssi.docker_ssi_matrix_utils import resolve_runtime_version
from utils._logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from docker.models.images import Image as DockerImage


_INSTALLER_SCRIPT_URL = "https://dd-agent.s3.amazonaws.com/scripts/install_script_agent7.sh"
_INSTALLER_SCRIPT_NAME = "install_script_agent7.sh"
_DIGEST_PATTERN = re.compile(r"^Digest:\s+(sha256:[0-9a-f]{64})\s*$", re.MULTILINE)


class DockerSSIImageError(RuntimeError):
    """Raised when Docker SSI image preparation fails."""


class DockerSSIImageBuilder:
    """Build the reusable and per-run Docker SSI image graphs with Rebuildr."""

    def __init__(
        self,
        scenario_name: str,
        host_log_folder: str,
        base_weblog: str,
        base_image: str,
        library: str,
        arch: str,
        installable_runtime: str | None,
        push_base_images: bool,  # noqa: FBT001
        env: str,
        custom_library_version: str | None,
        custom_injector_version: str | None,
        *,
        appsec_enabled: bool | None = None,
        root_dir: Path | None = None,
    ) -> None:
        self.scenario_name = scenario_name
        self.host_log_folder = host_log_folder
        self._base_weblog = base_weblog
        self._base_image = base_image
        self._library = library
        self._arch = arch
        self._installable_runtime = installable_runtime
        self._push_base_images = push_base_images
        self._env = env
        self._custom_library_version = custom_library_version
        self._custom_injector_version = custom_injector_version
        self._appsec_enabled = appsec_enabled
        self._root_dir = (root_dir or Path(__file__).resolve().parents[2]).resolve()
        log_folder = Path(host_log_folder)
        if not log_folder.is_absolute():
            log_folder = self._root_dir / log_folder
        self._log_folder = log_folder
        self._docker_build_log = log_folder / "docker_build.log"

        self._cached_build: Build | None = None
        self._cached_root: ImageHandle | None = None
        self._movable_build: Build | None = None
        self._movable_root: ImageHandle | None = None
        self._weblog_docker_image: DockerImage | None = None
        self._resolved_base_image: str | None = None
        self._installer_script_contents: bytes | None = None

    @property
    def dd_lang(self) -> str:
        return "js" if self._library == "nodejs" else self._library

    @property
    def cached_root(self) -> ImageHandle:
        if self._cached_root is None:
            raise DockerSSIImageError("Docker SSI image builder has not been configured")
        return self._cached_root

    @property
    def movable_root(self) -> ImageHandle:
        if self._movable_root is None:
            raise DockerSSIImageError("Docker SSI image builder has not been configured")
        return self._movable_root

    def configure(self) -> None:
        """Resolve mutable inputs and create immutable snapshots of both image DAGs."""
        self._validate_publication_policy()
        self._log_folder.mkdir(parents=True, exist_ok=True)
        self._resolved_base_image = self._resolve_base_image_digest()
        self._installer_script_contents = self._load_installer_script()

        installer_input, temporary_path = self._temporary_installer_script_input()
        try:
            self._cached_build = self._create_cached_build(installer_input)
            self._cached_root = Project(self._cached_build, self._root_dir).default
            self._movable_build = self._create_movable_build(installer_input)
            self._movable_root = Project(self._movable_build, self._root_dir).default
        finally:
            temporary_path.unlink(missing_ok=True)

        logger.stdout(
            f"Reusable Docker SSI image: {self.cached_root.uri} (source digest: {self.cached_root.source_digest})"
        )

    def build_weblog(self) -> None:
        """Materialize the reusable graph, rebuild the movable graph, and load its final image."""
        publish = self._is_gitlab_ci() or self._push_base_images
        if publish:
            try:
                self._run_rebuildr_action("Publish reusable Docker SSI image graph", self.cached_root.push)
            except Exception as error:
                raise DockerSSIImageError(
                    "Failed to publish reusable Docker SSI images. Verify registry authentication and inspect "
                    f"{self._docker_build_log}."
                ) from error
        else:
            try:
                self._run_rebuildr_action("Build or download reusable Docker SSI image graph", self.cached_root.build)
            except Exception as error:
                raise DockerSSIImageError(
                    "Failed to build or download reusable Docker SSI images. Verify Docker/registry access and "
                    f"inspect {self._docker_build_log}."
                ) from error

        try:
            final_image = self._run_rebuildr_action(
                "Build per-run Docker SSI and weblog image graph", self.movable_root.build
            )
        except Exception as error:
            raise DockerSSIImageError(
                f"Failed to build the Docker SSI weblog image. Inspect {self._docker_build_log}."
            ) from error

        try:
            self._weblog_docker_image = get_docker_client().images.get(final_image)
        except Exception as error:
            raise DockerSSIImageError(
                f"Rebuildr completed, but Docker could not retrieve the final image {final_image!r}."
            ) from error

    def tested_components(self) -> dict[str, str]:
        """Run the final image's component inventory script and parse its JSON output."""
        if self._weblog_docker_image is None:
            raise DockerSSIImageError("The Docker SSI weblog image has not been built")
        logger.info("Weblog extract tested components")
        result = get_docker_client().containers.run(
            image=self._weblog_docker_image,
            command=f"/tested_components.sh {self.dd_lang}",
            remove=True,
        )
        decoded = result.decode("utf-8")
        logger.info(f"Tested components: {decoded}")
        parsed = json.loads(decoded.replace("'", '"'))
        if not isinstance(parsed, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in parsed.items()
        ):
            raise DockerSSIImageError("The final Docker SSI image returned invalid tested-components JSON")
        return cast("dict[str, str]", parsed)

    def get_base_docker_tag(self) -> str:
        """Return the existing descriptive repository suffix for the reusable image."""
        runtime = (
            resolve_runtime_version(self._library, self._installable_runtime) + "_" if self._installable_runtime else ""
        )
        return f"{self._base_image}_{runtime}{self._arch}".replace(".", "_").replace(":", "-").replace("/", "-").lower()

    def _validate_publication_policy(self) -> None:
        if (self._is_gitlab_ci() or self._push_base_images) and not self._registry():
            source = "GitLab CI" if self._is_gitlab_ci() else "--ssi-push-base-images/-P"
            raise DockerSSIImageError(
                f"{source} requires PRIVATE_DOCKER_REGISTRY so reusable Docker SSI images can be published."
            )

    @staticmethod
    def _is_gitlab_ci() -> bool:
        return "GITLAB_CI" in os.environ

    @staticmethod
    def _registry() -> str:
        return os.getenv("PRIVATE_DOCKER_REGISTRY", "").rstrip("/")

    def _repository(self, name: str) -> str:
        registry = self._registry()
        return f"{registry}/system-tests/{name}" if registry else f"system-tests/{name}"

    def _resolve_base_image_digest(self) -> str:
        command = ["docker", "buildx", "imagetools", "inspect", self._base_image]
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            detail = ""
            if isinstance(error, subprocess.CalledProcessError):
                detail = (error.stderr or error.stdout or "").strip()
            suffix = f" Docker reported: {detail}" if detail else ""
            raise DockerSSIImageError(
                f"Failed to resolve base image {self._base_image!r} to an immutable registry digest. "
                f"Verify Docker registry access and the image name.{suffix}"
            ) from error

        match = _DIGEST_PATTERN.search(result.stdout)
        if match is None:
            raise DockerSSIImageError(
                f"Docker did not report an immutable digest for base image {self._base_image!r}. "
                "Run `docker buildx imagetools inspect <image>` to diagnose the registry response."
            )
        repository = self._base_image.split("@", maxsplit=1)[0]
        leaf_separator = repository.rfind("/")
        tag_separator = repository.rfind(":")
        if tag_separator > leaf_separator:
            repository = repository[:tag_separator]
        resolved = f"{repository}@{match.group(1)}"
        self._append_build_log(f"Resolved base image {self._base_image} to {resolved}\n")
        return resolved

    def _load_installer_script(self) -> bytes:
        candidates = (
            self._root_dir / "utils/build/ssi/base/binaries" / _INSTALLER_SCRIPT_NAME,
            self._root_dir / "binaries" / _INSTALLER_SCRIPT_NAME,
        )
        for candidate in candidates:
            if candidate.is_file():
                try:
                    contents = candidate.read_bytes()
                except OSError as error:
                    raise DockerSSIImageError(f"Failed to read installer script {candidate}.") from error
                if not contents:
                    raise DockerSSIImageError(f"Installer script {candidate} is empty.")
                self._append_build_log(f"Using installer script from {candidate}\n")
                return contents

        try:
            with urlopen(_INSTALLER_SCRIPT_URL, timeout=120) as response:  # noqa: S310
                contents = response.read()
        except (OSError, URLError) as error:
            raise DockerSSIImageError(
                f"Failed to download {_INSTALLER_SCRIPT_URL}. Check network access or provide "
                f"binaries/{_INSTALLER_SCRIPT_NAME}."
            ) from error
        if not contents:
            raise DockerSSIImageError(f"Downloaded installer script from {_INSTALLER_SCRIPT_URL} is empty.")
        self._append_build_log(f"Downloaded installer script from {_INSTALLER_SCRIPT_URL}\n")
        return contents

    def _temporary_installer_script_input(self) -> tuple[File, Path]:
        if self._installer_script_contents is None:
            raise DockerSSIImageError("Installer script contents have not been loaded")
        descriptor, name = tempfile.mkstemp(prefix=".docker-ssi-installer-", suffix=".sh", dir=self._root_dir)
        temporary_path = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as installer_file:
                installer_file.write(self._installer_script_contents)
            temporary_path.chmod(0o755)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        relative_path = temporary_path.relative_to(self._root_dir).as_posix()
        return File(relative_path, f"base/binaries/{_INSTALLER_SCRIPT_NAME}"), temporary_path

    def _create_cached_build(self, installer_script: File) -> Build:
        if self._resolved_base_image is None:
            raise DockerSSIImageError("Base image digest has not been resolved")
        docker_tag = self.get_base_docker_tag()
        build = Build(default="ssi-installer", platform=self._arch)

        base_context: list[File] = [
            self._file("utils/build/ssi/base/install_os_deps.sh", "base/install_os_deps.sh"),
            self._file("utils/build/ssi/base/healthcheck.sh", "base/healthcheck.sh"),
            self._file("utils/build/ssi/base/tested_components.sh", "base/tested_components.sh"),
        ]
        base_arguments = [
            BuildArg("BASE_IMAGE", self._resolved_base_image),
            BuildArg("ARCH", self._arch),
        ]
        if self._installable_runtime:
            dockerfile = "utils/build/ssi/base/base_lang.Dockerfile"
            runtime_script = f"utils/build/ssi/base/{self.dd_lang}_install_runtimes.sh"
            base_context.append(self._file(runtime_script, f"base/{self.dd_lang}_install_runtimes.sh"))
            base_arguments.extend(
                [
                    BuildArg("DD_LANG", self.dd_lang),
                    BuildArg("RUNTIME_VERSIONS", self._installable_runtime),
                ]
            )
        else:
            dockerfile = "utils/build/ssi/base/base_deps.Dockerfile"

        base = build.image(
            "base",
            repository=self._repository(f"ssi_base_{docker_tag}"),
            context=base_context,
            dockerfile=dockerfile,
            build_args=base_arguments,
        )
        build.image(
            "ssi-installer",
            repository=self._repository(f"ssi_installer_{docker_tag}"),
            context=[
                self._file(
                    "utils/build/ssi/base/install_script_ssi_installer.sh",
                    "base/install_script_ssi_installer.sh",
                ),
                installer_script,
            ],
            dockerfile="utils/build/ssi/base/base_ssi_installer.Dockerfile",
            image_refs={"cached-base": base},
            build_args=[BuildArg("BASE_IMAGE", "cached-base")],
            tag="latest",
        )
        return build

    def _create_movable_build(self, installer_script: File) -> Build:
        build = Build(default="weblog", platform=self._arch, content_tag=False)
        ssi_context = [
            self._file("utils/build/ssi/base/install_script_ssi.sh", "base/install_script_ssi.sh"),
            installer_script,
            *self._additional_binary_inputs(),
        ]
        ssi = build.image(
            "ssi",
            repository="system-tests/ssi-runtime",
            context=ssi_context,
            dockerfile="utils/build/ssi/base/base_ssi.Dockerfile",
            build_args=[
                BuildArg("BASE_IMAGE", self.cached_root.uri),
                BuildArg("DD_LANG", self.dd_lang),
                BuildArg("SSI_ENV", self._env),
                BuildArg("DD_INSTALLER_LIBRARY_VERSION", self._custom_library_version),
                BuildArg("DD_INSTALLER_INJECTOR_VERSION", self._custom_injector_version),
                BuildArg("DD_APPSEC_ENABLED", self._appsec_build_argument()),
                BuildArg("SSI_BUILD_NONCE", uuid.uuid4().hex),
            ],
        )
        weblog_context = [
            self._file(
                f"lib-injection/build/docker/{self._library}",
                f"lib-injection/build/docker/{self._library}",
            ),
            self._file(f"utils/build/ssi/{self._library}", f"utils/build/ssi/{self._library}"),
        ]
        build.image(
            "weblog",
            repository="weblog-injection",
            context=weblog_context,
            dockerfile=f"utils/build/ssi/{self._library}/{self._base_weblog}.Dockerfile",
            image_refs={"ssi-image": ssi},
            build_args=[BuildArg("BASE_IMAGE", "ssi-image")],
            tag="latest",
        )
        return build

    def _additional_binary_inputs(self) -> list[File]:
        binary_dir = self._root_dir / "utils/build/ssi/base/binaries"
        if not binary_dir.is_dir():
            return []
        inputs = []
        for source in sorted(binary_dir.iterdir()):
            if source.name == _INSTALLER_SCRIPT_NAME:
                continue
            relative = source.relative_to(self._root_dir).as_posix()
            inputs.append(File(relative, f"base/binaries/{source.name}"))
        return inputs

    def _appsec_build_argument(self) -> str | None:
        if isinstance(self._appsec_enabled, bool):
            return str(self._appsec_enabled).lower()
        return None

    @staticmethod
    def _file(source: str, target: str) -> File:
        return File(source, target)

    def _run_rebuildr_action(self, description: str, action: Callable[[], str]) -> str:
        self._log_folder.mkdir(parents=True, exist_ok=True)
        with self._docker_build_log.open("a", encoding="utf-8") as build_log:
            self._write_log_header(build_log, description)
            with redirect_stdout(build_log), redirect_stderr(build_log):
                try:
                    return action()
                except Exception as error:
                    build_log.write(f"{description} failed: {type(error).__name__}: {error}\n")
                    build_log.flush()
                    raise

    @staticmethod
    def _write_log_header(build_log: TextIO, description: str) -> None:
        build_log.write("\n***************************************************************\n")
        build_log.write(f"{description}\n")
        build_log.write("***************************************************************\n")
        build_log.flush()

    def _append_build_log(self, message: str) -> None:
        self._log_folder.mkdir(parents=True, exist_ok=True)
        with self._docker_build_log.open("a", encoding="utf-8") as build_log:
            build_log.write(message)
