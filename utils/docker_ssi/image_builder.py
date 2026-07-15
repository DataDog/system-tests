from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.error import URLError
from urllib.request import urlretrieve

from rebuildr import ImageHandle, load

from utils._context.docker import get_docker_client
from utils.docker_ssi.docker_ssi_matrix_utils import resolve_runtime_version

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from docker.models.images import Image as DockerImage


_INSTALLER_URL = "https://dd-agent.s3.amazonaws.com/scripts/install_script_agent7.sh"
_INSTALLER_NAME = "install_script_agent7.sh"
_REBUILDR_DIR = Path(__file__).parent


class DockerSSIImageError(RuntimeError):
    """Raised when Docker SSI image preparation fails."""


@dataclass
class DockerSSIImageBuilder:
    """Load and execute the reusable and per-run Docker SSI Rebuildr graphs."""

    host_log_folder: str
    base_weblog: str
    base_image: str
    library: str
    arch: str
    installable_runtime: str | None
    push_base_images: bool
    env: str
    custom_library_version: str | None
    custom_injector_version: str | None
    appsec_enabled: bool | None = None
    root_dir: Path | None = None
    cached_root: ImageHandle = field(init=False)
    movable_root: ImageHandle = field(init=False)
    _weblog_image: DockerImage | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._root_dir = (self.root_dir or Path(__file__).parents[2]).resolve()
        log_folder = Path(self.host_log_folder)
        self._log_folder = log_folder if log_folder.is_absolute() else self._root_dir / log_folder
        self._build_log = self._log_folder / "docker_build.log"

    @property
    def dd_lang(self) -> str:
        return "js" if self.library == "nodejs" else self.library

    def configure(self) -> None:
        if ("GITLAB_CI" in os.environ or self.push_base_images) and not os.getenv("PRIVATE_DOCKER_REGISTRY"):
            source = "GitLab CI" if "GITLAB_CI" in os.environ else "--ssi-push-base-images/-P"
            raise DockerSSIImageError(f"{source} requires PRIVATE_DOCKER_REGISTRY")
        self._log_folder.mkdir(parents=True, exist_ok=True)
        with self._installer_script() as installer:
            self.cached_root, self.movable_root = self._load_projects(self._resolve_base_image(), installer)

    def build_weblog(self) -> None:
        publish = "GITLAB_CI" in os.environ or self.push_base_images
        cached_action = self.cached_root.push if publish else self.cached_root.build
        self._run("Publish reusable images" if publish else "Build or download reusable images", cached_action)
        final_image = self._run("Build per-run SSI and weblog images", self.movable_root.build)
        self._weblog_image = get_docker_client().images.get(final_image)

    def tested_components(self) -> dict[str, str]:
        result = get_docker_client().containers.run(
            image=self._weblog_image, command=f"/tested_components.sh {self.dd_lang}", remove=True
        )
        return cast("dict[str, str]", json.loads(result.decode().replace("'", '"')))

    def _load_projects(self, base_image: str, installer: str) -> tuple[ImageHandle, ImageHandle]:
        registry = os.getenv("PRIVATE_DOCKER_REGISTRY", "").rstrip("/")
        values = {
            "REBUILDR_OVERRIDE_ROOT_DIR": str(self._root_dir),
            "DOCKER_SSI_PLATFORM": self.arch,
            "DOCKER_SSI_BASE_IMAGE": base_image,
            "DOCKER_SSI_DD_LANG": self.dd_lang,
            "DOCKER_SSI_RUNTIME": self.installable_runtime,
            "DOCKER_SSI_INSTALLER_SCRIPT": installer,
            "DOCKER_SSI_REPOSITORY_PREFIX": f"{registry}/system-tests" if registry else "system-tests",
            "DOCKER_SSI_BASE_TAG": self._base_tag(),
            "DOCKER_SSI_LIBRARY": self.library,
            "DOCKER_SSI_WEBLOG": self.base_weblog,
            "DOCKER_SSI_ENV": self.env,
            "DOCKER_SSI_LIBRARY_VERSION": self.custom_library_version,
            "DOCKER_SSI_INJECTOR_VERSION": self.custom_injector_version,
            "DOCKER_SSI_APPSEC_ENABLED": (
                str(self.appsec_enabled).lower() if isinstance(self.appsec_enabled, bool) else None
            ),
            "DOCKER_SSI_BUILD_NONCE": uuid.uuid4().hex,
            "DOCKER_SSI_CACHED_BASE_IMAGE": None,
        }
        previous = {name: os.environ.get(name) for name in values}
        try:
            os.environ.update({name: value or "" for name, value in values.items()})
            cached = load(_REBUILDR_DIR / "ssi-installer.rebuildr.py").default
            os.environ["DOCKER_SSI_CACHED_BASE_IMAGE"] = cached.uri
            return cached, load(_REBUILDR_DIR / "weblog-injection.rebuildr.py").default
        except Exception as error:
            raise DockerSSIImageError(f"Failed to load Docker SSI Rebuildr files: {error}") from error
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def _base_tag(self) -> str:
        runtime = (
            resolve_runtime_version(self.library, self.installable_runtime) + "_" if self.installable_runtime else ""
        )
        return f"{self.base_image}_{runtime}{self.arch}".replace(".", "_").replace(":", "-").replace("/", "-").lower()

    def _resolve_base_image(self) -> str:
        try:
            result = subprocess.run(
                ["docker", "buildx", "imagetools", "inspect", self.base_image, "--format", "{{.Manifest.Digest}}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise DockerSSIImageError(f"Failed to resolve registry digest for {self.base_image!r}") from error
        digest = result.stdout.strip()
        if not digest.startswith("sha256:"):
            raise DockerSSIImageError(f"Registry returned no digest for {self.base_image!r}")
        repository = self.base_image.split("@", maxsplit=1)[0]
        if repository.rfind(":") > repository.rfind("/"):
            repository = repository[: repository.rfind(":")]
        resolved = f"{repository}@{digest}"
        with self._build_log.open("a", encoding="utf-8") as build_log:
            build_log.write(f"Resolved {self.base_image} to {resolved}\n")
        return resolved

    @contextmanager
    def _installer_script(self) -> Iterator[str]:
        candidates = (
            self._root_dir / "utils/build/ssi/base/binaries" / _INSTALLER_NAME,
            self._root_dir / "binaries" / _INSTALLER_NAME,
        )
        local = next((path for path in candidates if path.is_file()), None)
        if local is not None:
            yield local.relative_to(self._root_dir).as_posix()
            return

        descriptor, name = tempfile.mkstemp(prefix=".docker-ssi-installer-", suffix=".sh", dir=self._root_dir)
        os.close(descriptor)
        temporary = Path(name)
        try:
            try:
                urlretrieve(_INSTALLER_URL, temporary)  # noqa: S310
            except (OSError, URLError) as error:
                raise DockerSSIImageError(f"Failed to download {_INSTALLER_URL}") from error
            yield temporary.relative_to(self._root_dir).as_posix()
        finally:
            temporary.unlink(missing_ok=True)

    def _run(self, description: str, action: Callable[[], str]) -> str:
        self._log_folder.mkdir(parents=True, exist_ok=True)
        with self._build_log.open("a", encoding="utf-8") as build_log:
            build_log.write(f"\n{'*' * 63}\n{description}\n{'*' * 63}\n")
            with redirect_stdout(build_log), redirect_stderr(build_log):
                try:
                    return action()
                except Exception as error:
                    raise DockerSSIImageError(f"{description} failed; inspect {self._build_log}") from error
