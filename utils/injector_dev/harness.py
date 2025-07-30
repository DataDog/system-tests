#!/usr/bin/env python3
# filepath: /Users/roberto.montero/Documents/development/system-tests/utils/injector_dev/harness.py
# Package harness provides testing utilities for injector-dev test assertions.

import logging
import yaml
import kubernetes as k8s
from kubernetes.stream import stream
from typing import Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    """Result represents the outcome of a test case."""

    passed: bool
    reason: str


class Deployment:
    """Deployment represents a Kubernetes deployment in the test harness."""

    def __init__(self, name: str, namespace: str, harness: "Harness"):
        self.name = name
        self.namespace = namespace
        self.harness = harness

    def has_env(self, key: str, value: str) -> tuple[Result, Exception | None]:
        """Check if the deployment has an environment variable with the specified value."""
        return self.harness.deployment_has_env(self.name, self.namespace, key, value)

    def does_not_have_env(self, key: str) -> tuple[Result, Exception | None]:
        """Check if the deployment does not have the specified environment variable."""
        return self.harness.deployment_does_not_have_env(self.name, self.namespace, key)

    def has_injection(self) -> tuple[Result, Exception | None]:
        """Check if the deployment has been injected."""
        return self.harness.deployment_has_injection(self.name, self.namespace)

    def has_no_injection(self) -> tuple[Result, Exception | None]:
        """Check if the deployment has not been injected."""
        return self.harness.deployment_has_no_injection(self.name, self.namespace)

    def has_init_containers(self, containers: list[str]) -> tuple[Result, Exception | None]:
        """Check if the deployment has the specified init containers."""
        return self.harness.deployment_has_init_containers(self.name, self.namespace, containers)

    def pod_has_env(self, env_name: str, env_value: str) -> tuple[Result, Exception | None]:
        """Check if a pod in the deployment has the specified environment variable."""
        return self.harness.pod_has_env(self.name, self.namespace, env_name, env_value)


class Harness:
    """Harness is a testing harness for injector-dev tests."""

    def __init__(
        self, scenario_provision: str | Path, k8s_client: dict[str, k8s.client.ApiClient], scenario: dict[str, Any]
    ):
        """Initialize a new Harness instance.

        Args:
            scenario_provision: Path to the scenario provision file (can be string or Path object)
            k8s_client: Kubernetes client APIs
            scenario: The loaded scenario data

        """
        # Convert Path to string if needed
        self.t = str(scenario_provision)
        self.k8s = k8s_client
        self.scenario = scenario

    @staticmethod
    def new(scenario_provision: str | Path) -> tuple["Harness", Exception | None]:
        """Create a new testing harness.

        Args:
            scenario_provision: Path to the scenario provision file (can be string or Path object)

        Returns:
            A tuple containing the harness and any error that occurred

        """
        k8s_client = {}  # Initialize outside try block to avoid unbound local error

        try:
            # Convert Path to string if needed
            scenario_provision_str = str(scenario_provision)

            # Load Kubernetes config
            k8s.config.load_kube_config()
            k8s_client = {
                "core": k8s.client.CoreV1Api(),
                "apps": k8s.client.AppsV1Api(),
            }

            # Load the scenario
            with open(scenario_provision_str, "r") as f:
                scenario = yaml.safe_load(f)

            # Validate scenario (simplified here)
            if not scenario:
                return Harness(scenario_provision_str, k8s_client, {}), ValueError("Empty scenario")

            logging.info(f"Loaded scenario at {scenario_provision_str}")
            return Harness(scenario_provision_str, k8s_client, scenario), None

        except Exception as e:
            # Make sure we convert Path to string here too
            scenario_provision_str = str(scenario_provision)
            return Harness(scenario_provision_str, k8s_client, {}), e

    @staticmethod
    def must(harness_tuple: tuple[Optional["Harness"], Exception | None]) -> "Harness":
        """Panic if there's an error, otherwise return the harness."""
        harness, err = harness_tuple
        if err:
            raise err
        if not harness:
            raise ValueError("Harness is None")
        return harness

    def require(self, result_tuple: tuple[Result, Exception | None]) -> None:
        """Require that a test result passes."""
        result, err = result_tuple
        assert err is None, f"Expected no error, but got one. {err}"
        assert result.passed, result.reason

    def deployment(self, name: str, namespace: str) -> Deployment:
        """Get a deployment from the harness."""
        return Deployment(name, namespace, self)

    def apps(self) -> list[dict[str, Any]]:
        """Get the apps from the scenario."""
        if not self.scenario:
            return []

        if self.scenario.get("helm"):
            return self.scenario["helm"].get("apps", [])

        if self.scenario.get("operator"):
            return self.scenario["operator"].get("apps", [])

        return []

    def get_pod_for_scenario_app(self, deployment: str, namespace: str) -> tuple[Any, Exception | None]:
        """Get a pod for a deployment that's defined in the scenario."""
        found = False
        for app in self.apps():
            if app.get("namespace") == namespace and app.get("name") == deployment:
                logging.info(f"Found app {namespace}/{deployment} in scenario")
                found = True
                break

        if not found:
            return None, ValueError(f"Scenario missing app definition {namespace}/{deployment}")

        try:
            # Get deployment
            deployment_obj = self.k8s["apps"].read_namespaced_deployment(deployment, namespace)

            # Get pod for deployment
            label_selector = ",".join([f"{k}={v}" for k, v in deployment_obj.spec.selector.match_labels.items()])
            pods = self.k8s["core"].list_namespaced_pod(namespace, label_selector=label_selector)

            if not pods.items:
                return None, ValueError(f"No pods found for deployment {namespace}/{deployment}")

            return pods.items[0], None

        except Exception as e:
            return None, e

    def deployment_has_init_containers(
        self, deployment: str, namespace: str, containers: list[str]
    ) -> tuple[Result, Exception | None]:
        """Check if a deployment has the specified init containers."""
        pod, err = self.get_pod_for_scenario_app(deployment, namespace)
        if err:
            return Result(passed=False, reason=f"Error getting pod: {err}"), err

        init_containers = {}
        if pod.spec.init_containers:
            for container in pod.spec.init_containers:
                init_containers[container.name] = True

        for container in containers:
            if container not in init_containers:
                return Result(
                    passed=False, reason=f"Init container {container} not found in {list(init_containers.keys())}"
                ), None

        return Result(passed=True, reason="Deployment has all init containers"), None

    def deployment_has_no_injection(self, deployment: str, namespace: str) -> tuple[Result, Exception | None]:
        """Check if a deployment has not been injected."""
        pod, err = self.get_pod_for_scenario_app(deployment, namespace)
        if err:
            return Result(passed=False, reason=f"Error getting pod: {err}"), err

        for container in pod.spec.containers:
            result, err = self.container_has_no_injection(container)
            if err:
                return Result(passed=False, reason=f"Error checking container injection: {err}"), err
            if not result.passed:
                return result, None

        return Result(passed=True, reason="Deployment has no injection"), None

    def container_has_no_injection(
        self, container: k8s.client.models.v1_container.V1Container
    ) -> tuple[Result, Exception | None]:
        """Check if a container has not been injected."""
        for env in container.env or []:
            if env.name == "LD_PRELOAD":
                return Result(passed=False, reason=f"{env.name} was set to {env.value}"), None

        return Result(passed=True, reason="Container has no injection"), None

    def deployment_has_injection(self, deployment: str, namespace: str) -> tuple[Result, Exception | None]:
        """Check if a deployment has been injected."""
        pod, err = self.get_pod_for_scenario_app(deployment, namespace)
        if err:
            return Result(passed=False, reason=f"Error getting pod: {err}"), err

        for container in pod.spec.containers:
            result, err = self.container_has_injection(container)
            if err:
                return Result(passed=False, reason=f"Error checking container injection: {err}"), err
            if not result.passed:
                return result, None

        return Result(passed=True, reason="Deployment has injection"), None

    def container_has_injection(
        self, container: k8s.client.models.v1_container.V1Container
    ) -> tuple[Result, Exception | None]:
        """Check if a container has been injected."""
        envs = self.env_map(container.env or [])

        if "LD_PRELOAD" not in envs:
            return Result(passed=False, reason="LD_PRELOAD was not set"), None

        if "DD_TRACE_AGENT_URL" not in envs:
            return Result(passed=False, reason="DD_TRACE_AGENT_URL was not set"), None

        if "DD_DOGSTATSD_URL" not in envs:
            return Result(passed=False, reason="DD_DOGSTATSD_URL was not set"), None

        return Result(passed=True, reason=f"Container {container.name} has been injected"), None

    def deployment_has_env(
        self, deployment: str, namespace: str, env_name: str, env_value: str
    ) -> tuple[Result, Exception | None]:
        """Check if a deployment has an environment variable with the specified value."""
        pod, err = self.get_pod_for_scenario_app(deployment, namespace)
        if err:
            return Result(passed=False, reason=f"Error getting pod: {err}"), err

        for container in pod.spec.containers:
            envs = self.env_map(container.env or [])
            if env_name not in envs:
                return Result(passed=False, reason=f"{env_name} was not set in {container.name}"), None

            if envs[env_name] != env_value:
                return Result(
                    passed=False,
                    reason=f"{env_name} was set to {envs[env_name]} in {container.name}, expected {env_value}",
                ), None

        return Result(passed=True, reason=f"{env_name} was set in all containers"), None

    def pod_has_env(
        self, deployment: str, namespace: str, env_name: str, env_value: str
    ) -> tuple[Result, Exception | None]:
        """Check if a pod has an environment variable with the specified value."""
        pod, err = self.get_pod_for_scenario_app(deployment, namespace)
        if err:
            return Result(passed=False, reason=f"Error getting pod: {err}"), err

        try:
            exec_command = ["sh", "-c", f"echo ${env_name}"]
            result = stream(
                self.k8s["core"].connect_get_namespaced_pod_exec,
                pod.metadata.name,
                namespace,
                command=exec_command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False,
            )

            stdout = ""
            while result.is_open():
                if result.peek_stdout():
                    stdout += result.read_stdout()
                if result.peek_stderr():
                    # Just consuming stderr
                    result.read_stderr()
                if not result.peek_stdout() and not result.peek_stderr():
                    break

            result.close()
            value = stdout.strip()

            if value == env_value:
                return Result(passed=True, reason=f"Found expected env var {env_value}"), None

            return Result(
                passed=False, reason=f"Found unexpected env var {env_name}={value}, expected {env_value}"
            ), None

        except Exception as e:
            return Result(passed=False, reason=f"Error checking pod environment: {e}"), e

    def deployment_does_not_have_env(
        self, deployment: str, namespace: str, env_name: str
    ) -> tuple[Result, Exception | None]:
        """Check if a deployment does not have the specified environment variable."""
        pod, err = self.get_pod_for_scenario_app(deployment, namespace)
        if err:
            return Result(passed=False, reason=f"Error getting pod: {err}"), err

        for container in pod.spec.containers:
            for env in container.env or []:
                if env.name == env_name:
                    return Result(passed=False, reason=f"{env_name} was set in {container.name}"), None

        return Result(passed=True, reason=f"{env_name} was not set in any containers"), None

    @staticmethod
    def env_map(env_vars: list[Any]) -> dict[str, str]:
        """Convert a list of environment variables to a map."""
        return {env.name: env.value for env in env_vars}
