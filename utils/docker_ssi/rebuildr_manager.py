"""Rebuildr Manager - A singleton client for managing Rebuildr operations.

This module provides a singleton RebuildrManager class that handles Rebuildr operations
including getting SHA256 signatures, building images, and pushing images to registries.
The class is designed to be generic and reusable for different types of images.
"""

import json
import logging
import os
import subprocess
import threading
from enum import Enum
from pathlib import Path
from typing import Optional

from docker.errors import BuildError
from utils.virtual_machine.vm_logger import vm_logger


class RebuildrOperation(Enum):
    """Enumeration of supported Rebuildr operations."""

    GET_SHA256 = "get_sha256"
    BUILD_IMAGE = "materialize-image"
    PUSH_IMAGE = "push-image"


class RebuildrConfig:
    """Configuration class for Rebuildr operations."""

    def __init__(
        self,
        config_file: str,
        image_repository: str,
        environment_vars: dict[str, str] | None = None,
        args: dict[str, str] | None = None,
    ) -> None:
        """Initialize Rebuildr configuration.

        Args:
            config_file: Path to the rebuildr configuration file (relative to working directory)
            image_repository: The image repository name to use
            environment_vars: Additional environment variables to set
            args: Additional arguments to pass to rebuildr

        """
        self.config_file = config_file
        self.image_repository = image_repository
        self.environment_vars = environment_vars or {}
        self.args = args or {}


class RebuildrManager:
    """Singleton manager for Rebuildr operations.

    This class provides a unified interface for executing Rebuildr commands
    to get SHA256 signatures, build images, and push images. It follows the
    singleton pattern to ensure consistent logging and configuration across
    the application.

    All rebuildr command output (stdout/stderr) is automatically logged to
    rebuildpr.log with clear separators for easy debugging and troubleshooting.
    """

    _instance: Optional["RebuildrManager"] = None
    _lock = threading.Lock()
    _initialized: bool

    def __new__(cls, *args: object, **kwargs: object) -> "RebuildrManager":
        """Create or return the singleton instance."""
        # Unused arguments are expected for singleton pattern
        del args, kwargs  # Explicitly delete to satisfy linter
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # Use setattr to avoid private member access warning
                    cls._instance._initialized = False  # noqa: SLF001
        return cls._instance

    def __init__(self, working_directory: str | Path = "utils/build/ssi/", host_log_folder: str = "logs") -> None:
        """Initialize the RebuildrManager singleton.

        Args:
            working_directory: The working directory where rebuildr commands will be executed
            host_log_folder: The directory where log files will be stored

        """
        if self._initialized:
            return

        self.working_directory = Path(working_directory)
        self.host_log_folder = host_log_folder
        self._logger = self._setup_logger()
        self._initialized = True

        self._logger.info("RebuildrManager singleton initialized")
        self._logger.info(f"Working directory: {self.working_directory}")
        self._logger.info(f"Log folder: {self.host_log_folder}")

    def _setup_logger(self) -> logging.Logger:
        """Set up the logger for Rebuildr operations."""
        return vm_logger(
            host_log_folder=self.host_log_folder, log_name="rebuildpr", level=logging.INFO, show_timestamp=True
        )

    def _raise_sha256_error(self) -> None:
        """Helper method to raise SHA256 error."""
        error_msg = "SHA256 field not found in rebuildr output"
        self._logger.error(error_msg)
        raise ValueError(error_msg)

    @classmethod
    def get_instance(
        cls, working_directory: str | Path = "utils/build/ssi/", host_log_folder: str = "logs"
    ) -> "RebuildrManager":
        """Get the singleton instance of RebuildrManager.

        Args:
            working_directory: The working directory (only used on first call)
            host_log_folder: The directory where log files will be stored (only used on first call)

        Returns:
            The singleton RebuildrManager instance

        """
        return cls(working_directory, host_log_folder)

    def get_sha256_signature(self, config: RebuildrConfig) -> str:
        """Get the SHA256 signature for an image configuration.

        Args:
            config: Rebuildr configuration object

        Returns:
            The SHA256 hash of the image configuration

        Raises:
            ValueError: If the SHA256 cannot be extracted from the output
            BuildError: If the rebuildr command fails

        """
        self._logger.info(f"Getting SHA256 signature for config: {config.config_file}")

        result = self._execute_rebuildr_command(config, RebuildrOperation.GET_SHA256)

        try:
            output_data = json.loads(result.stdout)
            sha256_value = output_data.get("sha256")

            if not sha256_value:
                self._raise_sha256_error()

            self._logger.info(f"Successfully extracted SHA256: {sha256_value}")
            return sha256_value

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON from rebuildr output: {e}"
            self._logger.exception(error_msg)
            raise ValueError(f"Invalid JSON in rebuildr output: {result.stdout}") from e
        except Exception as e:
            error_msg = f"Error extracting SHA256 from rebuildr output: {e}"
            self._logger.exception(error_msg)
            raise

    def build_image(self, config: RebuildrConfig) -> subprocess.CompletedProcess:
        """Build an image using the materialize-image command.

        Args:
            config: Rebuildr configuration object

        Returns:
            The completed subprocess result

        Raises:
            BuildError: If the rebuildr command fails

        """
        self._logger.info(f"Building image for config: {config.config_file}")
        result = self._execute_rebuildr_command(config, RebuildrOperation.BUILD_IMAGE)
        self._logger.info("Image build completed successfully")
        return result

    def push_image(self, config: RebuildrConfig) -> subprocess.CompletedProcess:
        """Push an image using the push-image command.

        Note: Automatically adds --only-content-id-tag parameter for push operations.

        Args:
            config: Rebuildr configuration object

        Returns:
            The completed subprocess result

        Raises:
            BuildError: If the rebuildr command fails

        """
        self._logger.info(f"Pushing image for config: {config.config_file}")
        result = self._execute_rebuildr_command(config, RebuildrOperation.PUSH_IMAGE)
        self._logger.info("Image push completed successfully")
        return result

    def build_and_push_image(self, config: RebuildrConfig) -> subprocess.CompletedProcess:
        """Build and push an image in one operation.

        Note: Automatically adds --only-content-id-tag parameter for push operations.

        Args:
            config: Rebuildr configuration object

        Returns:
            The completed subprocess result

        Raises:
            BuildError: If the rebuildr command fails

        """
        self._logger.info(f"Building and pushing image for config: {config.config_file}")
        result = self._execute_rebuildr_command(config, RebuildrOperation.PUSH_IMAGE)
        self._logger.info("Image build and push completed successfully")
        self._logger.info(f"Image build and push completed successfully: {result.stdout}")
        return result

    def _execute_rebuildr_command(
        self, config: RebuildrConfig, operation: RebuildrOperation
    ) -> subprocess.CompletedProcess:
        """Execute a rebuildr command with the specified operation.

        Args:
            config: Rebuildr configuration object
            operation: The operation to perform

        Returns:
            The completed subprocess result

        Raises:
            BuildError: If the rebuildr command fails

        """
        # Build the command
        cmd_parts = ["rebuildr", "load-py", config.config_file]

        # Add arguments if provided
        if config.args:
            for key, value in config.args.items():
                cmd_parts.append(f'{key}="{value}"')

        # Add operation-specific command
        if operation == RebuildrOperation.GET_SHA256:
            # For SHA256, we don't add materialize-image or push-image
            pass
        elif operation == RebuildrOperation.BUILD_IMAGE:
            cmd_parts.append("materialize-image")
        elif operation == RebuildrOperation.PUSH_IMAGE:
            cmd_parts.append("push-image")
            cmd_parts.append("--only-content-id-tag")  # Add parameter specifically for push operations
            self._logger.info("Added --only-content-id-tag parameter for push operation")

        # Set up environment variables
        env_vars = {"IMAGE_REPOSITORY": config.image_repository}
        env_vars.update(config.environment_vars)

        # Build environment for subprocess (include current environment)
        subprocess_env = os.environ.copy()
        subprocess_env.update(env_vars)

        # Log the command for debugging
        env_prefix = " ".join(f"{key}={value}" for key, value in env_vars.items())
        full_command_str = f"{env_prefix} {' '.join(cmd_parts)}"
        self._logger.info(f"Executing rebuildr command: {full_command_str}")

        # Execute the command without shell=True for security
        result = subprocess.run(
            cmd_parts, capture_output=True, text=True, cwd=str(self.working_directory), check=False, env=subprocess_env
        )

        # Handle the result
        if result.returncode == 0:
            self._logger.info("Rebuildr command executed successfully")
            if result.stdout:
                self._logger.info("--- REBUILDR STDOUT START ---")
                self._logger.info(result.stdout)
                self._logger.info("--- REBUILDR STDOUT END ---")
            if result.stderr:
                self._logger.info("--- REBUILDR STDERR START ---")
                self._logger.info(result.stderr)
                self._logger.info("--- REBUILDR STDERR END ---")
        else:
            error_msg = f"Rebuildr command failed with return code {result.returncode}"
            self._logger.error(error_msg)
            if result.stderr:
                self._logger.error("--- REBUILDR ERROR STDERR START ---")
                self._logger.error(result.stderr)
                self._logger.error("--- REBUILDR ERROR STDERR END ---")
            if result.stdout:
                self._logger.error("--- REBUILDR ERROR STDOUT START ---")
                self._logger.error(result.stdout)
                self._logger.error("--- REBUILDR ERROR STDOUT END ---")
            raise BuildError(f"Failed to execute rebuildr command: {result.stderr}", result.stderr)

        return result

    def create_custom_config(
        self,
        config_file: str,
        image_repository: str,
        environment_vars: dict[str, str] | None = None,
        args: dict[str, str] | None = None,
    ) -> RebuildrConfig:
        """Create a custom configuration for any rebuildr file.

        Args:
            config_file: Path to the rebuildr configuration file
            image_repository: The image repository name to use
            environment_vars: Additional environment variables
            args: Additional arguments to pass to rebuildr

        Returns:
            Custom RebuildrConfig

        """
        return RebuildrConfig(
            config_file=config_file, image_repository=image_repository, environment_vars=environment_vars, args=args
        )
