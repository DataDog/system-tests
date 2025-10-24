from collections.abc import Callable

from utils._logger import logger
from utils._context.docker import get_docker_client


class K8sComponentImage:
    """A class representing a Docker image with registry URL, version extraction, and URL/tag parsing.

    This class handles Docker image information including:
    - Registry URL parsing into main URL and tag components
    - Version extraction through a customizable extraction function
    - Caching of extracted version information

    Attributes:
        registry_url (str): The full Docker image URL including tag
        _version (Optional[str]): Cached version extracted from the image (lazy-loaded)
        _version_extractor (Callable[[str], str]): Function to extract version from image

    """

    def __init__(
        self,
        registry_url: str,
        version_extractor: Callable[[str], str],
        ssi_registry_base: str | None = None,
    ) -> None:
        """Initialize a K8sComponentImage instance.

        Args:
            registry_url: The full Docker image URL (e.g. 'gcr.io/datadoghq/apm-inject:latest')
            version_extractor: A function that takes a registry URL and returns the extracted version
            ssi_registry_base: Optional base registry URL to prepend to the registry_url

        """
        self.registry_url = registry_url
        self._version: str | None = None
        self._version_extractor = version_extractor
        self.ssi_registry_base = ssi_registry_base
        if self.ssi_registry_base:
            self.registry_url = f"{self.ssi_registry_base}/{self.registry_url}"

    @property
    def main_url(self) -> str:
        """Get the main URL part of the registry URL (without the tag).

        Returns:
            The main URL part of the registry URL

        """
        # Split the URL and tag at the last colon
        parts = self.registry_url.rsplit(":", 1)

        # If no colon or the part after the last colon contains a slash (not a tag),
        # then the whole string is the main URL
        if len(parts) == 1 or "/" in parts[1]:
            return self.registry_url

        # Otherwise, the first part is the main URL
        return parts[0]

    @property
    def tag(self) -> str:
        """Get the tag part of the registry URL.

        Returns:
            The tag part of the registry URL, or 'latest' if no tag is specified

        """
        # Split the URL and tag at the last colon
        parts = self.registry_url.rsplit(":", 1)

        # If no colon or the part after the last colon contains a slash (not a tag),
        # then return 'latest' as the default tag
        if len(parts) == 1 or "/" in parts[1]:
            return "latest"

        # Otherwise, the second part is the tag
        return parts[1]

    @property
    def version(self) -> str:
        """Get the version extracted from the Docker image.

        This property caches the result of the version extraction function
        to avoid repeated calls to Docker.

        Returns:
            The extracted version string

        Raises:
            ValueError: If version extraction fails

        """
        # Return cached version if available
        if self._version is not None:
            return self._version

        # Extract and cache version
        try:
            self._version = self._version_extractor(self.registry_url)
            return self._version
        except Exception as e:
            logger.error(f"Failed to extract version from image {self.registry_url}: {e}")
            raise ValueError(f"Failed to extract version from image {self.registry_url}: {e}") from e

    def __str__(self) -> str:
        """Return string representation of the K8sComponentImage."""
        return self.registry_url

    def __repr__(self) -> str:
        """Return detailed string representation of the K8sComponentImage."""
        return f"K8sComponentImage(registry_url='{self.registry_url}', version='{self._version or 'not extracted'}')"


# Commonly used version extractor functions


def extract_library_version(library_init_image: str) -> str:
    """Extract library version from a library init image.

    Args:
        library_init_image: The library init image URL

    Returns:
        The extracted version string

    Raises:
        ValueError: If version extraction fails

    """
    logger.info("Extracting library version from image")
    try:
        lib_init_docker_image = get_docker_client().images.pull(library_init_image)
        result = get_docker_client().containers.run(
            image=lib_init_docker_image, command="cat /datadog-init/package/version", remove=True
        )
        version = result.decode("utf-8").strip()
        logger.info(f"Library version: {version}")
        return version
    except Exception as e:
        logger.error(f"Failed to pull library init image: {library_init_image}")
        raise ValueError(f"Failed to extract library version: {e}") from e


def extract_injector_version(injector_image: str) -> str:
    """Extract injector version from an injector image.

    Args:
        injector_image: The injector image URL

    Returns:
        The extracted version string

    Raises:
        ValueError: If version extraction fails

    """
    logger.info(f"Extracting injector version from image: {injector_image}")
    try:
        injector_docker_image = get_docker_client().images.pull(injector_image)
        # The version is a folder name under /opt/datadog-packages/datadog-apm-inject/
        result = get_docker_client().containers.run(
            image=injector_docker_image, command="ls /opt/datadog-packages/datadog-apm-inject/", remove=True
        )
        version = result.decode("utf-8").split("\n")[0].strip()
        logger.info(f"Injector version: {version}")
        return version
    except Exception as e:
        logger.error(f"Failed to pull injector image: {injector_image}")
        raise ValueError(f"Failed to extract injector version: {e}") from e


def extract_cluster_agent_version(cluster_image: str) -> str:
    """Extract cluster agent version from a cluster agent image.

    Args:
        cluster_image: The cluster agent image URL

    Returns:
        The extracted version string

    Raises:
        ValueError: If version extraction fails

    """
    logger.info("Extracting cluster agent version")
    try:
        cluster_docker_image = get_docker_client().images.pull(cluster_image)
        version = cluster_docker_image.labels["org.opencontainers.image.version"]
        logger.info(f"Cluster agent version: {version}")
        return version
    except Exception as e:
        logger.error(f"Failed to pull cluster agent image: {cluster_image}")
        raise ValueError(f"Failed to extract cluster agent version: {e}") from e
