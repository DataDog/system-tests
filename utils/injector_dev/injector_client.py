#!/usr/bin/env python3
"""Module providing client for interacting with the injector-dev tool."""

import subprocess
from pathlib import Path

from utils._logger import logger


class InjectorDevClient:
    """Client for interacting with the injector-dev command-line tool.

    This class provides a clean interface to run operations with the injector-dev tool,
    handling command execution, logging, and error management.

    Attributes:
        injector_path: Path to the injector-dev executable

    """

    def __init__(self, injector_path: Path | None = None):
        """Initialize the injector client.

        Args:
            injector_path: Path to the injector-dev executable.
                           Defaults to 'binaries/injector-dev' if not provided.

        """
        self.injector_path = injector_path or Path("binaries") / "injector-dev"

        # Verify that the injector-dev tool exists
        if not self.injector_path.exists():
            raise FileNotFoundError(f"Injector-dev tool not found at {self.injector_path}. Please build it first.")

    def _run_command_with_logging(self, command: list[str], success_message: str, error_prefix: str) -> None:
        """Run a command with real-time logging of output.

        Args:
            command: The command to execute as a list of strings
            success_message: Message to log on successful execution
            error_prefix: Prefix for error message if execution fails

        Raises:
            RuntimeError: If the command execution fails

        """
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # Output real-time and log simultaneously
        if process.stdout is not None:
            for line in process.stdout:
                logger.stdout(line.strip())
        else:
            logger.warning("Unable to capture output from command (stdout is None)")

        process.wait()

        if process.returncode == 0:
            logger.info(success_message)
        else:
            error_message = f"{error_prefix} (exit code {process.returncode})"
            logger.error(error_message)
            raise RuntimeError(error_message)

    def start(self, *, debug: bool = False) -> None:
        """Start the injector-dev tool.

        Args:
            debug: Whether to start in debug mode

        Raises:
            RuntimeError: If the injector-dev tool fails to start

        """
        logger.info("Starting injector-dev tool")
        logger.info(f"Injector-dev tool found at {self.injector_path}. Starting it...")

        command = [str(self.injector_path), "start"]
        if debug:
            command.append("--debug")

        self._run_command_with_logging(
            command, "Injector-dev tool started successfully", "Failed to start injector-dev tool"
        )

    def stop(self, *, clean_k8s: bool = True) -> None:
        """Stop the injector-dev tool.

        Args:
            clean_k8s: Whether to also clean up Kubernetes resources (minikube, colima)

        """
        logger.info("Stopping injector-dev tool")
        logger.info(f"Injector-dev tool found at {self.injector_path}. Stopping it...")

        # Stop the injector-dev tool
        subprocess.run([str(self.injector_path), "stop"], check=False)

        # Clean up Kubernetes resources if requested
        if clean_k8s:
            subprocess.run(["minikube", "delete"], check=False)
            subprocess.run(["colima", "delete", "-f"], check=False)

        logger.info("Injector-dev tool stopped successfully")

    def apply_scenario(self, scenario_path: Path, *, wait: bool = True, debug: bool = False) -> None:
        """Apply a scenario to the injector-dev tool.

        Args:
            scenario_path: Path to the scenario YAML file
            wait: Whether to wait for the scenario to be applied
            debug: Whether to enable debug mode

        Raises:
            FileNotFoundError: If the scenario file doesn't exist
            RuntimeError: If the scenario application fails

        """
        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario file not found at {scenario_path}")

        logger.stdout(f"Applying scenario [{scenario_path.name}]...")

        command = [str(self.injector_path), "apply", "-f", str(scenario_path)]
        if wait:
            command.append("--wait")
        if debug:
            command.append("--debug")

        self._run_command_with_logging(
            command, "Scenario applied successfully", "Failed to apply scenario with injector-dev"
        )
