from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import uuid
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.error import URLError
from urllib.request import urlopen

from rebuildr import ImageHandle, load

from utils._context.docker import get_docker_client
from utils.docker_ssi.docker_ssi_matrix_utils import resolve_runtime_version
from utils._logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from docker.models.images import Image as DockerImage


_INSTALLER_SCRIPT_URL = "https://dd-agent.s3.amazonaws.com/scripts/install_script_agent7.sh"
_INSTALLER_SCRIPT_NAME = "install_script_agent7.sh"
_DIGEST_PATTERN = re.compile(r"^Digest:\s+(sha256:[0-9a-f]{64})\s*$", re.MULTILINE)
_REBUILDR_DIR = Path(__file__).resolve().parent
_CACHED_BUILD_FILE = _REBUILDR_DIR / "ssi-installer.rebuildr.py"
_MOVABLE_BUILD_FILE = _REBUILDR_DIR / "weblog-injection.rebuildr.py"


class DockerSSIImageError(RuntimeError):
    """Raised when Docker SSI image preparation fails."""


@contextmanager
def _rebuildr_environment(values: dict[str, str | None]) -> Iterator[None]:
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class DockerSSIImageBuilder:
    """Load and execute the cached and per-run Docker SSI Rebuildr graphs."""

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
        self._log_folder = log_folder if log_folder.is_absolute() else self._root_dir / log_folder
        self._docker_build_log = self._log_folder / "docker_build.log"
        self._cached_root: ImageHandle | None = None
        self._movable_root: ImageHandle | None = None
        self._weblog_docker_image: DockerImage | None = None

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
        """Resolve external inputs and load both Rebuildr files."""
        self._validate_publication_policy()
        self._log_folder.mkdir(parents=True, exist_ok=True)
        self._load_rebuildr_projects(self._resolve_base_image_digest(), self._load_installer_script())
        logger.stdout(
            f"Reusable Docker SSI image: {self.cached_root.uri} (source digest: {self.cached_root.source_digest})"
        )

    def build_weblog(self) -> None:
        """Materialize the reusable graph and always rebuild the per-run graph."""
        publish = self._is_gitlab_ci() or self._push_base_images
        description = (
            "Publish reusable Docker SSI image graph"
            if publish
            else "Build or download reusable Docker SSI image graph"
        )
        action = self.cached_root.push if publish else self.cached_root.build
        try:
            self._run_rebuildr_action(description, action)
        except Exception as error:
            action = "publish" if publish else "build or download"
            raise DockerSSIImageError(
                f"Failed to {action} reusable Docker SSI images. Verify Docker/registry access and inspect "
                f"{self._docker_build_log}."
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

    def _load_rebuildr_projects(self, resolved_base_image: str, installer_contents: bytes) -> None:
        with self._temporary_installer_script(installer_contents) as installer_script:
            values = {
                "REBUILDR_OVERRIDE_ROOT_DIR": str(self._root_dir),
                "DOCKER_SSI_PLATFORM": self._arch,
                "DOCKER_SSI_BASE_IMAGE": resolved_base_image,
                "DOCKER_SSI_DD_LANG": self.dd_lang,
                "DOCKER_SSI_RUNTIME": self._installable_runtime,
                "DOCKER_SSI_INSTALLER_SCRIPT": installer_script,
                "DOCKER_SSI_REPOSITORY_PREFIX": self._repository_prefix(),
                "DOCKER_SSI_BASE_TAG": self._base_tag(),
                "DOCKER_SSI_LIBRARY": self._library,
                "DOCKER_SSI_WEBLOG": self._base_weblog,
                "DOCKER_SSI_ENV": self._env,
                "DOCKER_SSI_LIBRARY_VERSION": self._custom_library_version,
                "DOCKER_SSI_INJECTOR_VERSION": self._custom_injector_version,
                "DOCKER_SSI_APPSEC_ENABLED": self._appsec_build_argument(),
                "DOCKER_SSI_BUILD_NONCE": uuid.uuid4().hex,
                "DOCKER_SSI_CACHED_BASE_IMAGE": None,
            }
            try:
                with _rebuildr_environment(values):
                    self._cached_root = load(_CACHED_BUILD_FILE).default
                    os.environ["DOCKER_SSI_CACHED_BASE_IMAGE"] = self.cached_root.uri
                    self._movable_root = load(_MOVABLE_BUILD_FILE).default
            except Exception as error:
                raise DockerSSIImageError(
                    f"Failed to load {_CACHED_BUILD_FILE.name} or {_MOVABLE_BUILD_FILE.name}: {error}"
                ) from error

    def _validate_publication_policy(self) -> None:
        gitlab_ci = self._is_gitlab_ci()
        if (gitlab_ci or self._push_base_images) and not self._registry():
            source = "GitLab CI" if gitlab_ci else "--ssi-push-base-images/-P"
            raise DockerSSIImageError(
                f"{source} requires PRIVATE_DOCKER_REGISTRY so reusable Docker SSI images can be published."
            )

    @staticmethod
    def _is_gitlab_ci() -> bool:
        return "GITLAB_CI" in os.environ

    @staticmethod
    def _registry() -> str:
        return os.getenv("PRIVATE_DOCKER_REGISTRY", "").rstrip("/")

    def _repository_prefix(self) -> str:
        registry = self._registry()
        return f"{registry}/system-tests" if registry else "system-tests"

    def _base_tag(self) -> str:
        runtime = (
            resolve_runtime_version(self._library, self._installable_runtime) + "_" if self._installable_runtime else ""
        )
        return f"{self._base_image}_{runtime}{self._arch}".replace(".", "_").replace(":", "-").replace("/", "-").lower()

    def _resolve_base_image_digest(self) -> str:
        try:
            result = subprocess.run(
                ["docker", "buildx", "imagetools", "inspect", self._base_image],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            detail = (
                (error.stderr or error.stdout or "").strip() if isinstance(error, subprocess.CalledProcessError) else ""
            )
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
        if repository.rfind(":") > repository.rfind("/"):
            repository = repository[: repository.rfind(":")]
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

    @contextmanager
    def _temporary_installer_script(self, contents: bytes) -> Iterator[str]:
        descriptor, name = tempfile.mkstemp(prefix=".docker-ssi-installer-", suffix=".sh", dir=self._root_dir)
        path = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as installer_file:
                installer_file.write(contents)
            path.chmod(0o755)
            yield path.relative_to(self._root_dir).as_posix()
        finally:
            path.unlink(missing_ok=True)

    def _appsec_build_argument(self) -> str | None:
        return str(self._appsec_enabled).lower() if isinstance(self._appsec_enabled, bool) else None

    def _run_rebuildr_action(self, description: str, action: Callable[[], str]) -> str:
        self._log_folder.mkdir(parents=True, exist_ok=True)
        with self._docker_build_log.open("a", encoding="utf-8") as build_log:
            build_log.write("\n***************************************************************\n")
            build_log.write(f"{description}\n")
            build_log.write("***************************************************************\n")
            build_log.flush()
            with redirect_stdout(build_log), redirect_stderr(build_log):
                try:
                    return action()
                except Exception as error:
                    build_log.write(f"{description} failed: {type(error).__name__}: {error}\n")
                    build_log.flush()
                    raise

    def _append_build_log(self, message: str) -> None:
        self._log_folder.mkdir(parents=True, exist_ok=True)
        with self._docker_build_log.open("a", encoding="utf-8") as build_log:
            build_log.write(message)
