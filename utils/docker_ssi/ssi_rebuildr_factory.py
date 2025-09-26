"""SSI Rebuildr Configuration Factory.

This module provides a factory class for creating SSI-specific Rebuildr configurations.
It separates SSI-specific logic from the generic RebuildrManager, following the
Factory design pattern for clean separation of concerns.
"""

from .rebuildr_manager import RebuildrConfig


class SSIRebuildrFactory:
    """Factory class for creating SSI-specific Rebuildr configurations.

    This class encapsulates all SSI-specific knowledge and configuration logic,
    keeping the RebuildrManager generic and reusable for other use cases.

    Uses the Factory pattern to provide a clean interface for creating
    different types of SSI-related image configurations.
    """

    @staticmethod
    def create_base_deps_config(
        image_repository: str, base_image: str, additional_env_vars: dict[str, str] | None = None
    ) -> RebuildrConfig:
        """Create a configuration for building base dependencies images.

        This configuration is used for images that only install basic system
        dependencies without any language runtime or SSI components.

        Args:
            image_repository: The image repository name to use
            base_image: The base image to build from (e.g., "ubuntu:22.04")
            additional_env_vars: Additional environment variables to set

        Returns:
            RebuildrConfig configured for base dependencies

        Example:
            >>> config = SSIRebuildrFactory.create_base_deps_config(
            ...     image_repository="my-deps-image",
            ...     base_image="ubuntu:22.04"
            ... )

        """
        return RebuildrConfig(
            config_file="base/base_deps.rebuildr.py",
            image_repository=image_repository,
            environment_vars=additional_env_vars or {},
            args={"BASE_IMAGE": base_image},
        )

    @staticmethod
    def create_ssi_installer_config(
        image_repository: str,
        base_image: str,
        dd_api_key: str = "xxxxxxxxxx",
        additional_env_vars: dict[str, str] | None = None,
    ) -> RebuildrConfig:
        """Create a configuration for building SSI installer images.

        This configuration is used for images that install the Datadog SSI
        installer on top of a base image, preparing it for auto-instrumentation.

        Args:
            image_repository: The image repository name to use
            base_image: The base image to build from
            dd_api_key: The Datadog API key to use for installation
            additional_env_vars: Additional environment variables to set

        Returns:
            RebuildrConfig configured for SSI installer

        Example:
            >>> config = SSIRebuildrFactory.create_ssi_installer_config(
            ...     image_repository="registry.com/ssi-installer",
            ...     base_image="my-deps:latest",
            ...     dd_api_key="real_api_key_here"
            ... )

        """
        return RebuildrConfig(
            config_file="base/base_ssi_installer.rebuildr.py",
            image_repository=image_repository,
            environment_vars=additional_env_vars or {},
            args={"BASE_IMAGE": base_image, "DD_API_KEY": dd_api_key},
        )

    @staticmethod
    def create_ssi_config(
        image_repository: str,
        base_image: str,
        dd_api_key: str = "deadbeef",
        dd_lang: str = "",
        ssi_env: str = "",
        dd_installer_library_version: str = "",
        dd_installer_injector_version: str = "",
        dd_appsec_enabled: str = "",
        additional_env_vars: dict[str, str] | None = None,
    ) -> RebuildrConfig:
        """Create a configuration for building full SSI images.

        This configuration is used for images that have the complete SSI
        auto-instrumentation setup, ready to automatically instrument
        applications at runtime.

        Args:
            image_repository: The image repository name to use
            base_image: The SSI installer image to build from
            dd_api_key: The Datadog API key to use
            dd_lang: The language for instrumentation (e.g., "java", "python", "js")
            ssi_env: The SSI environment (e.g., "prod", "staging")
            dd_installer_library_version: Specific library version to install
            dd_installer_injector_version: Specific injector version to install
            dd_appsec_enabled: Whether to enable Application Security ("true"/"false")
            additional_env_vars: Additional environment variables to set

        Returns:
            RebuildrConfig configured for full SSI auto-instrumentation

        Example:
            >>> config = SSIRebuildrFactory.create_ssi_config(
            ...     image_repository="my-app-ssi",
            ...     base_image="registry.com/ssi-installer:tag",
            ...     dd_lang="java",
            ...     ssi_env="production",
            ...     dd_appsec_enabled="true"
            ... )

        """
        return RebuildrConfig(
            config_file="base/base_ssi.rebuildr.py",
            image_repository=image_repository,
            environment_vars=additional_env_vars or {},
            args={
                "BASE_IMAGE": base_image,
                "DD_API_KEY": dd_api_key,
                "DD_LANG": dd_lang,
                "SSI_ENV": ssi_env,
                "DD_INSTALLER_LIBRARY_VERSION": dd_installer_library_version,
                "DD_INSTALLER_INJECTOR_VERSION": dd_installer_injector_version,
                "DD_APPSEC_ENABLED": dd_appsec_enabled,
            },
        )
