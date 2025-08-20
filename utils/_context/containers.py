import os
import re
import stat
import json
from typing import cast
from http import HTTPStatus
from pathlib import Path
from subprocess import run
import time
from functools import lru_cache
from threading import RLock, Thread

import docker
from docker.errors import APIError, DockerException
from docker.models.containers import Container, ExecResult
from docker.models.networks import Network
import pytest
import requests

from utils._context.component_version import ComponentVersion
from utils.proxy.ports import ProxyPorts
from utils._logger import logger
from utils import interfaces
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog
from utils.interfaces._library.core import LibraryInterfaceValidator
from utils.interfaces import StdoutLogsInterface, LibraryStdoutInterface

# fake key of length 32
_FAKE_DD_API_KEY = "0123456789abcdef0123456789abcdef"


@lru_cache
def _get_client():
    try:
        return docker.DockerClient.from_env()
    except DockerException as e:
        # Failed to start the default Docker client... Let's see if we have
        # better luck with docker contexts...
        try:
            ctx_name = run(["docker", "context", "show"], capture_output=True, check=True, text=True).stdout.strip()
            endpoint = run(
                ["docker", "context", "inspect", ctx_name, "-f", "{{ .Endpoints.docker.Host }}"],
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
            return docker.DockerClient(base_url=endpoint)
        except:
            logger.exception("Fail to get docker client with context")

        if "Error while fetching server API version: ('Connection aborted.'" in str(e):
            pytest.exit("Connection refused to docker daemon, is it running?", 1)

        raise


_DEFAULT_NETWORK_NAME = "system-tests_default"
_NETWORK_NAME = "bridge" if "GITLAB_CI" in os.environ else _DEFAULT_NETWORK_NAME


def create_network() -> Network:
    for network in _get_client().networks.list(names=[_NETWORK_NAME]):
        logger.debug(f"Network {_NETWORK_NAME} still exists")
        return network

    logger.debug(f"Create network {_NETWORK_NAME}")
    return _get_client().networks.create(_NETWORK_NAME, check_duplicate=True)


_VOLUME_INJECTOR_NAME = "volume-inject"


def create_inject_volume():
    logger.debug(f"Create volume {_VOLUME_INJECTOR_NAME}")
    _get_client().volumes.create(_VOLUME_INJECTOR_NAME)


class TestedContainer:
    _container: Container = None

    # https://docker-py.readthedocs.io/en/stable/containers.html
    def __init__(
        self,
        name: str,
        image_name: str,
        *,
        allow_old_container: bool = False,
        cap_add: list[str] | None = None,
        command: str | list[str] | None = None,
        environment: dict[str, str | None] | None = None,
        healthcheck: dict | None = None,
        host_log_folder: str,
        local_image_only: bool = False,
        ports: dict | None = None,
        security_opt: list[str] | None = None,
        stdout_interface: StdoutLogsInterface | None = None,
        user: str | None = None,
        volumes: dict | None = None,
        working_dir: str | None = None,
    ) -> None:
        self.name = name
        self.host_project_dir = os.environ.get("SYSTEM_TESTS_HOST_PROJECT_DIR", str(Path.cwd()))
        self.host_log_folder = host_log_folder
        self.allow_old_container = allow_old_container

        self.image = ImageInfo(image_name, local_image_only=local_image_only)
        self.healthcheck = healthcheck

        # healthy values:
        # None: container did not tried to start yet, or hasn't be started for another reason
        # False: container is not healthy
        # True: container is healthy
        self.healthy: bool | None = None

        self.environment = environment or {}
        self.volumes = volumes or {}
        self.ports = ports or {}
        self.depends_on: list[TestedContainer] = []
        self._starting_lock = RLock()
        self._starting_thread: Thread | None = None
        self.stdout_interface = stdout_interface
        self.working_dir = working_dir
        self.command = command
        self.user = user
        self.cap_add = cap_add
        self.security_opt = security_opt
        self.ulimits: list | None = None
        self.privileged = False

    def enable_core_dumps(self) -> None:
        """Modify container options to enable the possibility of core dumps"""

        self.cap_add = self.cap_add if self.cap_add is not None else []

        if "SYS_PTRACE" not in self.cap_add:
            self.cap_add.append("SYS_PTRACE")
        if "SYS_ADMIN" not in self.cap_add:
            self.cap_add.append("SYS_ADMIN")

        self.privileged = True
        self.ulimits = [docker.types.Ulimit(name="core", soft=-1, hard=-1)]

    def get_image_list(self, library: str, weblog: str) -> list[str]:  # noqa: ARG002
        """Returns the image list that will be loaded to be able to run/build the container"""
        return [self.image.name]

    def configure(self, *, replay: bool):
        if not replay:
            self.stop_previous_container()

            Path(self.log_folder_path).mkdir(exist_ok=True, parents=True)
            Path(f"{self.log_folder_path}/logs").mkdir(exist_ok=True, parents=True)

            self.image.load()
            self.image.save_image_info(self.log_folder_path)
        else:
            self.image.load_from_logs(self.log_folder_path)

    @property
    def container_name(self):
        return f"system-tests-{self.name}"

    @property
    def log_folder_path(self):
        return f"{self.host_project_dir}/{self.host_log_folder}/docker/{self.name}"

    def get_existing_container(self) -> Container:
        for container in _get_client().containers.list(all=True, filters={"name": self.container_name}):
            if container.name == self.container_name:
                logger.debug(f"Container {self.container_name} found")
                return container

        return None

    def stop_previous_container(self):
        if self.allow_old_container:
            return

        if old_container := self.get_existing_container():
            logger.debug(f"Kill old container {self.container_name}")
            old_container.remove(force=True)

    def start(self, network: Network) -> Container:
        """Start the actual underlying Docker container directly"""

        if self._container:
            # container is already started, some scenarios actively starts some containers
            # before calling async_start()
            return

        if old_container := self.get_existing_container():
            if self.allow_old_container:
                self._container = old_container
                logger.debug(f"Use old container {self.container_name}")

                old_container.restart()

                return

            raise ValueError("Old container still exists")

        self._fix_host_pwd_in_volumes()

        logger.info(f"Start container {self.container_name}")

        self._container = _get_client().containers.run(
            image=self.image.name,
            name=self.container_name,
            hostname=self.name,
            environment=self.environment,
            # auto_remove=True,
            detach=True,
            network=network.name,
            volumes=self.volumes,
            ports=self.ports,
            working_dir=self.working_dir,
            command=self.command,
            user=self.user,
            cap_add=self.cap_add,
            security_opt=self.security_opt,
            privileged=self.privileged,
            ulimits=self.ulimits,
        )

        self.healthy = self.wait_for_health()
        if self.healthy:
            self.warmup()

        self._container.reload()
        # with open(f"{self.log_folder_path}/container.json", "w", encoding="utf-8") as f:
        #     json.dump(self._container.attrs, f, indent=2)

    def async_start(self, network: Network) -> Thread:
        """Start the container and its dependencies in a thread with circular dependency detection"""
        self.check_circular_dependencies([])

        return self.async_start_recursive(network)

    def network_ipv6(self, network: Network) -> str:
        self._container.reload()
        return self._container.attrs["NetworkSettings"]["Networks"][network.name]["GlobalIPv6Address"]

    def network_ip(self, network: Network) -> str:
        self._container.reload()
        return self._container.attrs["NetworkSettings"]["Networks"][network.name]["IPAddress"]

    def check_circular_dependencies(self, seen: list):
        """Check if the container has a circular dependency"""
        if self in seen:
            dependencies = " -> ".join([s.name for s in seen] + [self.name])
            raise RuntimeError(f"Circular dependency detected between containers: {dependencies}")

        seen.append(self)

        for dependency in self.depends_on:
            dependency.check_circular_dependencies(list(seen))

    def async_start_recursive(self, network: Network):
        """Recursive version of async_start for circular dependency detection"""
        with self._starting_lock:
            if self._starting_thread is None:
                self._starting_thread = Thread(
                    target=self._start_with_dependencies, name=f"start_{self.name}", kwargs={"network": network}
                )
                self._starting_thread.start()

        return self._starting_thread

    def _start_with_dependencies(self, network: Network):
        """Start all dependencies of a container and then start the container"""
        threads = [dependency.async_start_recursive(network) for dependency in self.depends_on]

        for thread in threads:
            thread.join()

        for dependency in self.depends_on:
            if not dependency.healthy:
                return

        # this function is executed in a thread
        # the main thread will take care of the exception
        try:
            self.start(network)
        except Exception as e:
            logger.exception(f"Error while starting {self.name}: {e}")
            self.healthy = False

    def warmup(self):
        """If some stuff must be done after healthcheck"""

    def post_start(self):
        """If some stuff must be done after the container is started"""

    @property
    def healthcheck_log_file(self):
        return f"{self.log_folder_path}/healthcheck.log"

    def wait_for_health(self) -> bool:
        if self.healthcheck:
            exit_code, output = self.execute_command(**self.healthcheck)

            with open(self.healthcheck_log_file, "w", encoding="utf-8") as f:
                f.write(output)

            if exit_code != 0:
                logger.stdout(f"Healthcheck failed for {self.name}:\n{output}")
                return False

            logger.info(f"Healthcheck successful for {self.name}")

        return True

    def exec_run(self, cmd: str, *, demux: bool = False) -> ExecResult:
        return self._container.exec_run(cmd, demux=demux)

    def execute_command(
        self, test: str, retries: int = 10, interval: float = 1_000_000_000, start_period: float = 0
    ) -> tuple[int, str]:
        """Execute a command inside a container. Useful for healthcheck and warmups.
        test is a command to be executed, interval, timeout and start_period are in us (microseconds)
        This function does not raise any exception, it returns a tuple with the exit code and the output
        The exit code is 0 (success) or any other integer (failure)

        Note that timeout is not supported by the docker SDK
        """

        cmd = test

        if not isinstance(cmd, str):
            assert cmd[0] == "CMD-SHELL", "Only CMD-SHELL is supported"
            cmd = cmd[1]

        interval = interval / 1_000_000_000
        start_period = start_period / 1_000_000_000

        if start_period:
            time.sleep(start_period)

        logger.info(f"Executing command {cmd} for {self.name}")

        result = None

        for i in range(retries + 1):
            try:
                result = self._container.exec_run(cmd)

                logger.debug(f"Try #{i} for {self.name}: {result}")

                if result.exit_code == 0:
                    break

            except APIError as e:
                logger.exception(f"Try #{i} failed")
                return 1, f"Command {cmd} failed for {self._container.name}: {e.explanation}"

            except Exception as e:
                logger.debug(f"Try #{i}: {e}")

            self._container.reload()
            if self._container.status != "running":
                return 1, f"Container {self._container.name} is not running"

            time.sleep(interval)

        if not result:
            return 1, f"Command {cmd} can't be executed for {self._container.name}"

        return result.exit_code, result.output.decode("utf-8")

    def _fix_host_pwd_in_volumes(self):
        # on docker compose, volume host path can starts with a "."
        # it means the current path on host machine. It's not supported in bare docker
        # replicate this behavior here
        host_pwd = self.host_project_dir

        result = {}
        for host_path, container_path in self.volumes.items():
            if host_path.startswith("./"):
                corrected_host_path = f"{host_pwd}{host_path[1:]}"
                result[corrected_host_path] = container_path
            else:
                result[host_path] = container_path

        self.volumes = result

    def stop(self):
        self._starting_thread = None

        if self._container:
            self._container.reload()
            if self._container.status != "running":
                self.healthy = False
                pytest.exit(f"Container {self.name} is not running, please check logs", 1)

            self._container.stop()

            if not self.healthy:
                pytest.exit(f"Container {self.name} is not healthy, please check logs", 1)

    def collect_logs(self):
        TAIL_LIMIT = 50  # noqa: N806
        SEP = "=" * 30  # noqa: N806

        data = (
            ("stdout", self._container.logs(stdout=True, stderr=False)),
            ("stderr", self._container.logs(stdout=False, stderr=True)),
        )
        for output_name, raw_output in data:
            filename = f"{self.log_folder_path}/{output_name}.log"
            with open(filename, "wb") as f:
                f.write(raw_output)

            if not self.healthy:
                decoded_output = raw_output.decode("utf-8")

                logger.stdout(f"\n{SEP} {self.name} {output_name.upper()} last {TAIL_LIMIT} lines {SEP}")
                logger.stdout(f"-> See {filename} for full logs")
                logger.stdout("")
                # print last <tail> lines in stdout
                logger.stdout("\n".join(decoded_output.splitlines()[-TAIL_LIMIT:]))
                logger.stdout("")

    def remove(self):
        logger.debug(f"Removing container {self.name}")

        if self._container:
            try:
                # collect logs before removing
                self.collect_logs()
                self._container.remove(force=True)
            except:
                # Sometimes, the container does not exists.
                # We can safely ignore this, because if it's another issue
                # it will be killed at startup
                logger.info(f"Fail to remove container {self.name}")

        if self.stdout_interface is not None:
            self.stdout_interface.load_data()

    def _set_aws_auth_environment(self):
        # copy SYSTEM_TESTS_AWS env variables from local env to docker image

        if "SYSTEM_TESTS_AWS_ACCESS_KEY_ID" in os.environ:
            prefix = "SYSTEM_TESTS_AWS"
            for key, value in os.environ.items():
                if prefix in key:
                    self.environment[key.replace("SYSTEM_TESTS_", "")] = value
        else:
            prefix = "AWS"
            for key, value in os.environ.items():
                if prefix in key:
                    self.environment[key] = value

        # Set default AWS values if specific keys are not present
        if "AWS_REGION" not in self.environment:
            self.environment["AWS_REGION"] = "us-east-1"
            self.environment["AWS_DEFAULT_REGION"] = "us-east-1"

        if "AWS_SECRET_ACCESS_KEY" not in self.environment:
            self.environment["AWS_SECRET_ACCESS_KEY"] = "not-secret"  # noqa: S105

        if "AWS_ACCESS_KEY_ID" not in self.environment:
            self.environment["AWS_ACCESS_KEY_ID"] = "not-secret"


class SqlDbTestedContainer(TestedContainer):
    def __init__(
        self,
        name: str,
        *,
        image_name: str,
        host_log_folder: str,
        db_user: str,
        environment: dict[str, str | None] | None = None,
        allow_old_container: bool = False,
        healthcheck: dict | None = None,
        stdout_interface: StdoutLogsInterface | None = None,
        command: str | None = None,
        ports: dict | None = None,
        user: str | None = None,
        volumes: dict | None = None,
        cap_add: list[str] | None = None,
        db_password: str | None = None,
        db_instance: str | None = None,
        db_host: str | None = None,
        dd_integration_service: str | None = None,
    ) -> None:
        super().__init__(
            image_name=image_name,
            name=name,
            host_log_folder=host_log_folder,
            environment=environment,
            stdout_interface=stdout_interface,
            healthcheck=healthcheck,
            allow_old_container=allow_old_container,
            ports=ports,
            command=command,
            user=user,
            volumes=volumes,
            cap_add=cap_add,
        )
        self.dd_integration_service = dd_integration_service
        self.db_user = db_user
        self.db_password = db_password
        self.db_host = db_host
        self.db_instance = db_instance


class ImageInfo:
    """data on docker image. data comes from `docker inspect`"""

    def __init__(self, image_name: str, *, local_image_only: bool):
        # local_image_only: boolean
        # True if the image is only available locally and can't be loaded from any hub

        self.env: dict[str, str] | None = None
        self.labels: dict[str, str] = {}
        self.name = image_name
        self.local_image_only = local_image_only

    def load(self):
        try:
            self._image = _get_client().images.get(self.name)
        except docker.errors.ImageNotFound:
            if self.local_image_only:
                pytest.exit(f"Image {self.name} not found locally, please build it", 1)

            logger.stdout(f"Pulling {self.name}")
            try:
                self._image = _get_client().images.pull(self.name)
            except docker.errors.ImageNotFound:
                # Sometimes pull returns ImageNotFound, internal race?
                time.sleep(5)
                self._image = _get_client().images.pull(self.name)

        self._init_from_attrs(self._image.attrs)

    def load_from_logs(self, dir_path: str):
        with open(f"{dir_path}/image.json", encoding="utf-8") as f:
            attrs = json.load(f)

        self._init_from_attrs(attrs)

    def _init_from_attrs(self, attrs: dict):
        self.env = {}
        for var in attrs["Config"]["Env"]:
            key, value = var.split("=", 1)
            if value:
                self.env[key] = value

        if "Labels" in attrs["Config"]:
            self.labels = attrs["Config"]["Labels"]

    def save_image_info(self, dir_path: str):
        with open(f"{dir_path}/image.json", encoding="utf-8", mode="w") as f:
            json.dump(self._image.attrs, f, indent=2)


class ProxyContainer(TestedContainer):
    command_host_port = 11111  # Which port exposed to host to sent proxy commands

    def __init__(
        self,
        *,
        host_log_folder: str,
        rc_api_enabled: bool,
        meta_structs_disabled: bool,
        span_events: bool,
        enable_ipv6: bool,
    ) -> None:
        """Parameters:
        span_events: Whether the agent supports the native serialization of span events

        """

        # Adjust healthcheck for IPv6 scenarios
        host_target = "::1" if enable_ipv6 else "localhost"
        socket_family = "socket.AF_INET6" if enable_ipv6 else "socket.AF_INET"

        super().__init__(
            image_name="datadog/system-tests:proxy-v1",
            name="proxy",
            host_log_folder=host_log_folder,
            environment={
                "DD_SITE": os.environ.get("DD_SITE"),
                "DD_API_KEY": os.environ.get("DD_API_KEY", _FAKE_DD_API_KEY),
                "DD_APP_KEY": os.environ.get("DD_APP_KEY"),
                "SYSTEM_TESTS_HOST_LOG_FOLDER": host_log_folder,
                "SYSTEM_TESTS_RC_API_ENABLED": str(rc_api_enabled),
                "SYSTEM_TESTS_AGENT_SPAN_META_STRUCTS_DISABLED": str(meta_structs_disabled),
                "SYSTEM_TESTS_AGENT_SPAN_EVENTS": str(span_events),
                "SYSTEM_TESTS_IPV6": str(enable_ipv6),
            },
            working_dir="/app",
            volumes={
                f"./{host_log_folder}/interfaces/": {"bind": f"/app/{host_log_folder}/interfaces", "mode": "rw"},
                "./utils/": {"bind": "/app/utils/", "mode": "ro"},
            },
            ports={f"{ProxyPorts.proxy_commands}/tcp": ("127.0.0.1", self.command_host_port)},
            command="python utils/proxy/core.py",
            healthcheck={
                "test": f"python -c \"import socket; s=socket.socket({socket_family}); s.settimeout(2); s.connect(('{host_target}', {ProxyPorts.weblog})); s.close()\"",  # noqa: E501
                "retries": 30,
            },
        )


class LambdaProxyContainer(TestedContainer):
    def __init__(
        self,
        *,
        host_log_folder: str,
        lambda_weblog_host: str,
        lambda_weblog_port: str,
    ) -> None:
        from utils import weblog

        self.host_port = weblog.port
        self.container_port = "7777"

        super().__init__(
            image_name="system_tests/lambda-proxy",
            name="lambda-proxy",
            host_log_folder=host_log_folder,
            environment={
                "RIE_HOST": lambda_weblog_host,
                "RIE_PORT": lambda_weblog_port,
            },
            ports={
                f"{self.host_port}/tcp": self.container_port,
            },
            healthcheck={
                "test": f"curl --fail --silent --show-error --max-time 2 localhost:{self.container_port}/healthcheck",
                "retries": 60,
            },
            local_image_only=True,
        )


class AgentContainer(TestedContainer):
    apm_receiver_port: int = 8127
    dogstatsd_port: int = 8125

    def __init__(
        self, host_log_folder: str, *, use_proxy: bool = True, environment: dict[str, str | None] | None = None
    ) -> None:
        environment = environment or {}
        environment.update(
            {
                "DD_ENV": "system-tests",
                "DD_HOSTNAME": "test",
                "DD_SITE": self.dd_site,
                "DD_APM_RECEIVER_PORT": str(self.apm_receiver_port),
                "DD_DOGSTATSD_PORT": str(self.dogstatsd_port),
                "DD_API_KEY": os.environ.get("DD_API_KEY", _FAKE_DD_API_KEY),
            }
        )

        if use_proxy:
            environment["DD_PROXY_HTTPS"] = f"http://proxy:{ProxyPorts.agent}"
            environment["DD_PROXY_HTTP"] = f"http://proxy:{ProxyPorts.agent}"

        super().__init__(
            image_name=self._get_image_name(),
            name="agent",
            host_log_folder=host_log_folder,
            environment=environment,
            healthcheck={
                "test": f"curl --fail --silent --show-error --max-time 2 http://localhost:{self.apm_receiver_port}/info",
                "retries": 60,
            },
            stdout_interface=interfaces.agent_stdout,
            volumes={
                # this certificate comes from utils/proxy/.mitmproxy/mitmproxy-ca-cert.cer
                "./utils/build/docker/agent/ca-certificates.crt": {
                    "bind": "/etc/ssl/certs/ca-certificates.crt",
                    "mode": "ro",
                },
                "./utils/build/docker/agent/datadog.yaml": {"bind": "/etc/datadog-agent/datadog.yaml", "mode": "ro"},
            },
        )

        self.agent_version: str | None = ""

    def _get_image_name(self) -> str:
        try:
            with open("binaries/agent-image", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return "datadog/agent:latest"

    def post_start(self):
        with open(self.healthcheck_log_file, encoding="utf-8") as f:
            data = json.load(f)

        self.agent_version = ComponentVersion("agent", data["version"]).version

        logger.stdout(f"Agent: {self.agent_version}")
        logger.stdout(f"Backend: {self.dd_site}")

    @property
    def dd_site(self):
        return os.environ.get("DD_SITE", "datad0g.com")


class BuddyContainer(TestedContainer):
    def __init__(
        self,
        name: str,
        image_name: str,
        host_log_folder: str,
        host_port: int,
        trace_agent_port: int,
        environment: dict[str, str | None],
    ) -> None:
        super().__init__(
            name=name,
            image_name=image_name,
            host_log_folder=host_log_folder,
            healthcheck={"test": "curl --fail --silent --show-error --max-time 2 localhost:7777", "retries": 60},
            ports={"7777/tcp": host_port},
            environment={
                **environment,
                "DD_SERVICE": name,
                "DD_ENV": "system-tests",
                "DD_VERSION": "1.0.0",
                # "DD_TRACE_DEBUG": "true",
                "DD_AGENT_HOST": "proxy",
                "DD_TRACE_AGENT_PORT": str(trace_agent_port),
                "SYSTEM_TESTS_AWS_URL": "http://localstack-main:4566",
            },
        )

        self._set_aws_auth_environment()

    @property
    def interface(self) -> LibraryInterfaceValidator:
        result = getattr(interfaces, self.name)
        assert result is not None, "Interface is not set"
        return result


class WeblogContainer(TestedContainer):
    appsec_rules_file: str | None
    stdout_interface: LibraryStdoutInterface
    _dd_rc_tuf_root: dict = {
        "signed": {
            "_type": "root",
            "spec_version": "1.0",
            "version": 1,
            "expires": "2032-05-29T12:49:41.030418-04:00",
            "keys": {
                "ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e": {
                    "keytype": "ed25519",
                    "scheme": "ed25519",
                    "keyid_hash_algorithms": ["sha256", "sha512"],
                    "keyval": {"public": "7d3102e39abe71044d207550bda239c71380d013ec5a115f79f51622630054e6"},
                }
            },
            "roles": {
                "root": {
                    "keyids": ["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],
                    "threshold": 1,
                },
                "snapshot": {
                    "keyids": ["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],
                    "threshold": 1,
                },
                "targets": {
                    "keyids": ["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],
                    "threshold": 1,
                },
                "timestsmp": {
                    "keyids": ["ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e"],
                    "threshold": 1,
                },
            },
            "consistent_snapshot": True,
        },
        "signatures": [
            {
                "keyid": "ed7672c9a24abda78872ee32ee71c7cb1d5235e8db4ecbf1ca28b9c50eb75d9e",
                "sig": "d7e24828d1d3104e48911860a13dd6ad3f4f96d45a9ea28c4a0f04dbd3ca6c205ed406523c6c4cacfb7ebba68f7e122e42746d1c1a83ffa89c8bccb6f7af5e06",  # noqa: E501
            }
        ],
    }

    def __init__(
        self,
        host_log_folder: str,
        *,
        environment: dict[str, str | None] | None = None,
        tracer_sampling_rate: float | None = None,
        appsec_enabled: bool = True,
        iast_enabled: bool = True,
        runtime_metrics_enabled: bool = False,
        additional_trace_header_tags: tuple[str, ...] = (),
        use_proxy: bool = True,
        volumes: dict | None = None,
    ) -> None:
        from utils import weblog

        self.host_port = weblog.port
        self.container_port = 7777

        self.host_grpc_port = weblog.grpc_port
        self.container_grpc_port = 7778

        volumes = {} if volumes is None else volumes
        volumes[f"./{host_log_folder}/docker/weblog/logs/"] = {"bind": "/var/log/system-tests", "mode": "rw"}

        base_environment: dict[str, str | None] = {
            # Datadog setup
            "DD_SERVICE": "weblog",
            "DD_VERSION": "1.0.0",
            "DD_TAGS": "key1:val1,key2:val2",
            "DD_ENV": "system-tests",
            "DD_TRACE_LOG_DIRECTORY": "/var/log/system-tests",
            # for remote configuration tests
            "DD_RC_TUF_ROOT": json.dumps(self._dd_rc_tuf_root),
        }

        # Basic env set for all scenarios
        base_environment["DD_TELEMETRY_METRICS_ENABLED"] = "true"
        base_environment["DD_TELEMETRY_HEARTBEAT_INTERVAL"] = self.telemetry_heartbeat_interval

        # Python lib has different env var until we enable Telemetry Metrics by default
        base_environment["_DD_TELEMETRY_METRICS_ENABLED"] = "true"
        base_environment["DD_TELEMETRY_METRICS_INTERVAL_SECONDS"] = self.telemetry_heartbeat_interval

        if runtime_metrics_enabled:
            base_environment["DD_RUNTIME_METRICS_ENABLED"] = "true"

        if appsec_enabled:
            base_environment["DD_APPSEC_ENABLED"] = "true"
            base_environment["DD_APPSEC_WAF_TIMEOUT"] = "10000000"  # 10 seconds
            base_environment["DD_APPSEC_TRACE_RATE_LIMIT"] = "10000"

        if iast_enabled:
            base_environment["DD_IAST_ENABLED"] = "true"
            # Python lib has Code Security debug env var
            base_environment["_DD_IAST_DEBUG"] = "true"
            base_environment["DD_IAST_REQUEST_SAMPLING"] = "100"
            base_environment["DD_IAST_MAX_CONCURRENT_REQUESTS"] = "10"
            base_environment["DD_IAST_DEDUPLICATION_ENABLED"] = "false"
            base_environment["DD_IAST_VULNERABILITIES_PER_REQUEST"] = "10"
            base_environment["DD_IAST_MAX_CONTEXT_OPERATIONS"] = "10"

        if tracer_sampling_rate:
            base_environment["DD_TRACE_SAMPLE_RATE"] = str(tracer_sampling_rate)
            base_environment["DD_TRACE_SAMPLING_RULES"] = json.dumps([{"sample_rate": tracer_sampling_rate}])

        if use_proxy:
            # set the tracer to send data to runner (it will forward them to the agent)
            base_environment["DD_AGENT_HOST"] = "proxy"
            base_environment["DD_TRACE_AGENT_PORT"] = self.trace_agent_port
        else:
            base_environment["DD_AGENT_HOST"] = "agent"
            base_environment["DD_TRACE_AGENT_PORT"] = str(AgentContainer.apm_receiver_port)

        # overwrite values with those set in the scenario
        environment = base_environment | (environment or {})

        super().__init__(
            image_name="system_tests/weblog",
            name="weblog",
            host_log_folder=host_log_folder,
            environment=environment,
            volumes=volumes,
            # ddprof's perf event open is blocked by default by docker's seccomp profile
            # This is worse than the line above though prevents mmap bugs locally
            security_opt=["seccomp=unconfined"],
            healthcheck={
                "test": f"curl --fail --silent --show-error --max-time 2 localhost:{self.container_port}/healthcheck",
                "retries": 60,
            },
            ports={
                f"{self.host_port}/tcp": self.container_port,
                f"{self.host_grpc_port}/tcp": self.container_grpc_port,
            },
            stdout_interface=interfaces.library_stdout,
            local_image_only=True,
            command="./app.sh",
        )

        self.tracer_sampling_rate = tracer_sampling_rate
        self.additional_trace_header_tags = additional_trace_header_tags

        self.weblog_variant = ""
        self._library: ComponentVersion | None = None

    @property
    def trace_agent_port(self):
        return ProxyPorts.weblog

    @staticmethod
    def _get_image_list_from_dockerfile(dockerfile: str) -> list[str]:
        result = []

        pattern = re.compile(r"FROM\s+(?P<image_name>[^ ]+)")
        with open(dockerfile, encoding="utf-8") as f:
            for line in f:
                if match := pattern.match(line):
                    result.append(match.group("image_name"))

        return result

    def get_image_list(self, library: str | None, weblog: str | None) -> list[str]:
        """Returns images needed to build the weblog"""

        # If an image is saved as a file in binaries, we don't need any image
        filename = f"binaries/{library}-{weblog}-weblog.tar.gz"
        if Path(filename).is_file():
            return []

        # else, parse the Dockerfile and extract all images reference in a FROM section"""
        result: list[str] = []

        if not library or not weblog:
            return result

        args = {}

        pattern = re.compile(r"^FROM\s+(?P<image_name>[^\s]+)")
        arg_pattern = re.compile(r"^ARG\s+(?P<arg_name>[^\s]+)\s*=\s*(?P<arg_value>[^\s]+)")
        with open(f"utils/build/docker/{library}/{weblog}.Dockerfile", encoding="utf-8") as f:
            for line in f:
                if match := arg_pattern.match(line):
                    args[match.group("arg_name")] = match.group("arg_value")

                if match := pattern.match(line):
                    image_name = match.group("image_name")

                    for name, value in args.items():
                        image_name = image_name.replace(f"${name}", value)

                    result.append(image_name)

        return result

    def configure(self, *, replay: bool):
        super().configure(replay=replay)

        self.weblog_variant = self.image.labels["system-tests-weblog-variant"]

        self._set_aws_auth_environment()

        library = self.image.labels["system-tests-library"]

        header_tags = ""
        if library in ("cpp_nginx", "cpp_httpd", "dotnet", "java", "python"):
            header_tags = "user-agent:http.request.headers.user-agent"
        elif library in ("golang", "nodejs", "php", "ruby"):
            header_tags = "user-agent"
        else:
            header_tags = ""

        if library == "ruby" and "rails" in self.weblog_variant:
            # Ensure ruby on rails apps log to stdout
            self.environment["RAILS_LOG_TO_STDOUT"] = "true"

        if len(self.additional_trace_header_tags) != 0:
            header_tags += f',{",".join(self.additional_trace_header_tags)}'

        self.environment["DD_TRACE_HEADER_TAGS"] = header_tags

        if "DD_APPSEC_RULES" in self.environment:
            self.appsec_rules_file = self.environment["DD_APPSEC_RULES"]
        elif self.image.env is not None and "DD_APPSEC_RULES" in self.environment:
            self.appsec_rules_file = self.image.env["DD_APPSEC_RULES"]
        else:
            self.appsec_rules_file = None

        # Workaround: Once the dd-trace-go fix is merged that avoids a go panic for
        # DD_TRACE_PROPAGATION_EXTRACT_FIRST=true when context propagation fails,
        # we can remove the DD_TRACE_PROPAGATION_EXTRACT_FIRST=false override
        if library == "golang":
            self.environment["DD_TRACE_PROPAGATION_EXTRACT_FIRST"] = "false"

        # Workaround: We may want to define baggage in our list of propagators, but the cpp library
        # has strict checks on tracer startup that will fail to launch the application
        # when it encounters unfamiliar configurations. Override the configuration that the cpp
        # weblog container sees so we can still run tests
        if library in ("cpp_nginx", "cpp_httpd"):
            extract_config = self.environment.get("DD_TRACE_PROPAGATION_STYLE_EXTRACT")
            if extract_config and "baggage" in extract_config:
                self.environment["DD_TRACE_PROPAGATION_STYLE_EXTRACT"] = extract_config.replace("baggage", "").strip(
                    ","
                )
            # specify if the scenario is DD_TRACE_PROPAGATION_DEFAULT
            # then use the default configuration values

        if library == "nodejs":
            try:
                with open("./binaries/nodejs-load-from-local", encoding="utf-8") as f:
                    path = f.read().strip(" \r\n")
                    path_str = str(Path(path).resolve())
                    self.volumes[path_str] = {
                        "bind": "/volumes/dd-trace-js",
                        "mode": "ro",
                    }
            except Exception:
                logger.info("No local dd-trace-js found")

        if library == "php":
            self.enable_core_dumps()

    def post_start(self):
        from utils import weblog

        logger.debug(f"Docker host is {weblog.domain}")

        with open(self.healthcheck_log_file, encoding="utf-8") as f:
            data = json.load(f)
            lib = data["library"]

        self._library = ComponentVersion(lib["name"], lib["version"])

        logger.stdout(f"Library: {self.library}")

        if self.appsec_rules_file:
            logger.stdout("Using a custom appsec rules file")

        if self.uds_mode:
            logger.stdout(f"UDS socket: {self.uds_socket}")

        logger.stdout(f"Weblog variant: {self.weblog_variant}")

        self.stdout_interface.init_patterns(self.library)

    @property
    def library(self) -> ComponentVersion:
        assert self._library is not None, "Library version is not set"
        return self._library

    @property
    def uds_socket(self):
        assert self.image.env is not None, "No env set"
        return self.image.env.get("DD_APM_RECEIVER_SOCKET", None)

    @property
    def uds_mode(self):
        return self.uds_socket is not None

    @property
    def telemetry_heartbeat_interval(self):
        return 2


class LambdaWeblogContainer(WeblogContainer):
    def __init__(
        self,
        host_log_folder: str,
        *,
        environment: dict[str, str | None] | None = None,
        volumes: dict | None = None,
    ):
        environment = (environment or {}) | {
            "DD_HOSTNAME": "test",
            "DD_SITE": os.environ.get("DD_SITE", "datad0g.com"),
            "DD_API_KEY": os.environ.get("DD_API_KEY", _FAKE_DD_API_KEY),
            "DD_SERVERLESS_FLUSH_STRATEGY": "periodically,100",
            "DD_TRACE_MANAGED_SERVICES": "false",
        }

        volumes = volumes or {}

        environment["DD_PROXY_HTTPS"] = f"http://proxy:{ProxyPorts.agent}"
        environment["DD_LOG_LEVEL"] = "debug"
        volumes.update(
            {
                "./utils/build/docker/agent/ca-certificates.crt": {
                    "bind": "/etc/ssl/certs/ca-certificates.crt",
                    "mode": "ro",
                },
                "./utils/build/docker/agent/datadog.yaml": {
                    "bind": "/var/task/datadog.yaml",
                    "mode": "ro",
                },
            }
        )

        super().__init__(
            host_log_folder,
            environment=environment,
            volumes=volumes,
        )

        # Set the container port to the one used by the one of the Lambda RIE
        self.container_port = 8080

        # Replace healthcheck with a custom one for Lambda
        healthcheck_event = json.dumps({"healthcheck": True})
        self.healthcheck = {
            "test": f"curl --fail --silent --show-error --max-time 2 -XPOST -d '{healthcheck_event}' http://localhost:{self.container_port}/2015-03-31/functions/function/invocations",
            "retries": 60,
        }
        # Remove port bindings, as only the LambdaProxyContainer needs to expose a server
        self.ports = {}


class PostgresContainer(SqlDbTestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="postgres:alpine",
            name="postgres",
            host_log_folder=host_log_folder,
            healthcheck={"test": "pg_isready -q -U postgres -d system_tests_dbname", "retries": 30},
            user="postgres",
            environment={"POSTGRES_PASSWORD": "password", "PGPORT": "5433"},
            volumes={
                "./utils/build/docker/postgres-init-db.sh": {
                    "bind": "/docker-entrypoint-initdb.d/init_db.sh",
                    "mode": "ro",
                }
            },
            stdout_interface=interfaces.postgres,
            dd_integration_service="postgresql",
            db_user="system_tests_user",
            db_password="system_tests",  # noqa: S106
            db_host="postgres",
            db_instance="system_tests_dbname",
        )


class MongoContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="mongo:latest", name="mongodb", host_log_folder=host_log_folder, allow_old_container=True
        )


class KafkaContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            # TODO: Look into apache/kafka-native but it doesn't include scripts.
            image_name="apache/kafka:3.7.1",
            name="kafka",
            host_log_folder=host_log_folder,
            environment={
                "KAFKA_PROCESS_ROLES": "broker,controller",
                "KAFKA_NODE_ID": "1",
                "KAFKA_LISTENERS": "PLAINTEXT://:9092,CONTROLLER://:9093",
                "KAFKA_CONTROLLER_QUORUM_VOTERS": "1@kafka:9093",
                "KAFKA_CONTROLLER_LISTENER_NAMES": "CONTROLLER",
                "CLUSTER_ID": "5L6g3nShT-eMCtK--X86sw",
                "KAFKA_ADVERTISED_LISTENERS": "PLAINTEXT://kafka:9092",
                "KAFKA_INTER_BROKER_LISTENER_NAME": "PLAINTEXT",
                "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT",
                "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
                "KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS": "0",
            },
            allow_old_container=True,
            healthcheck={
                "test": ["CMD-SHELL", "/opt/kafka/bin/kafka-topics.sh --bootstrap-server 127.0.0.1:9092 --list"],
                "start_period": 1 * 1_000_000_000,
                "interval": 1 * 1_000_000_000,
                # "timeout": 1 * 1_000_000_000,
                "retries": 30,
            },
        )

    def warmup(self):
        topic = "dsm-system-tests-queue"
        server = "127.0.0.1:9092"

        kafka_options = f"--topic {topic} --bootstrap-server {server}"

        commands = [
            f"/opt/kafka/bin/kafka-topics.sh --create {kafka_options}",
            f'bash -c "echo hello | /opt/kafka/bin/kafka-console-producer.sh {kafka_options}"',
            f"/opt/kafka/bin/kafka-console-consumer.sh {kafka_options} --max-messages 1 --group testgroup1 --from-beginning",  # noqa: E501
        ]

        for command in commands:
            exit_code, output = self.execute_command(test=command, interval=1 * 1_000_000_000, retries=30)
            if exit_code != 0:
                logger.stdout(f"Command {command} failed for {self._container.name}: {output}")
                self.healthy = False
                return


class CassandraContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="cassandra:latest",
            name="cassandra_db",
            host_log_folder=host_log_folder,
            allow_old_container=True,
        )


class RabbitMqContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="rabbitmq:3.12-management-alpine",
            name="rabbitmq",
            host_log_folder=host_log_folder,
            allow_old_container=True,
            ports={"5672": ("127.0.0.1", 5672)},
        )


class ElasticMQContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="softwaremill/elasticmq-native:1.6.11",
            name="elasticmq",
            host_log_folder=host_log_folder,
            environment={"ELASTICMQ_OPTS": "-Dnode-address.hostname=0.0.0.0"},
            ports={9324: 9324},
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
            allow_old_container=True,
        )


class LocalstackContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="localstack/localstack:4.1",
            name="localstack-main",
            environment={
                "LOCALSTACK_SERVICES": "kinesis,sqs,sns,xray",
                "EXTRA_CORS_ALLOWED_HEADERS": "x-amz-request-id,x-amzn-requestid,x-amzn-trace-id",
                "EXTRA_CORS_EXPOSE_HEADERS": "x-amz-request-id,x-amzn-requestid,x-amzn-trace-id",
                "AWS_DEFAULT_REGION": "us-east-1",
                "FORCE_NONINTERACTIVE": "true",
                "START_WEB": "0",
                "DEBUG": "1",
                "SQS_PROVIDER": "elasticmq",
                "DOCKER_HOST": "unix:///var/run/docker.sock",
            },
            host_log_folder=host_log_folder,
            ports={"4566": ("127.0.0.1", 4566)},
            volumes={"/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"}},
        )


class MySqlContainer(SqlDbTestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="mysql/mysql-server:latest",
            name="mysqldb",
            command="--default-authentication-plugin=mysql_native_password",
            environment={
                "MYSQL_DATABASE": "mysql_dbname",
                "MYSQL_USER": "mysqldb",
                "MYSQL_ROOT_PASSWORD": "mysqldb",
                "MYSQL_PASSWORD": "mysqldb",
            },
            allow_old_container=True,
            host_log_folder=host_log_folder,
            healthcheck={"test": "/healthcheck.sh", "retries": 60},
            dd_integration_service="mysql",
            db_user="mysqldb",
            db_password="mysqldb",  # noqa: S106
            db_host="mysqldb",
            db_instance="mysql_dbname",
        )


class MsSqlServerContainer(SqlDbTestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        self.data_mssql = f"./{host_log_folder}/data-mssql"

        healthcheck = {
            # Using 127.0.0.1 here instead of localhost to avoid using IPv6 in some systems.
            # -C : trust self signed certificates
            "test": '/opt/mssql-tools18/bin/sqlcmd -S 127.0.0.1 -U sa -P "yourStrong(!)Password" -Q "SELECT 1" -b -C',
            "retries": 20,
        }

        super().__init__(
            image_name="mcr.microsoft.com/mssql/server:2022-latest",
            name="mssql",
            cap_add=["SYS_PTRACE"],
            user="root",
            environment={"ACCEPT_EULA": "1", "MSSQL_SA_PASSWORD": "yourStrong(!)Password"},
            allow_old_container=True,
            host_log_folder=host_log_folder,
            ports={"1433/tcp": ("127.0.0.1", 1433)},
            #  volumes={self.data_mssql: {"bind": "/var/opt/mssql/data", "mode": "rw"}},
            healthcheck=healthcheck,
            dd_integration_service="mssql",
            db_user="SA",
            db_password="yourStrong(!)Password",  # noqa: S106
            db_host="mssql",
            db_instance="master",
        )


class OpenTelemetryCollectorContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        image = os.environ.get("SYSTEM_TESTS_OTEL_COLLECTOR_IMAGE", "otel/opentelemetry-collector-contrib:0.110.0")
        self._otel_config_host_path = "./utils/build/docker/otelcol-config.yaml"

        if "DOCKER_HOST" in os.environ:
            m = re.match(r"(?:ssh:|tcp:|fd:|)//(?:[^@]+@|)([^:]+)", os.environ["DOCKER_HOST"])
            if m is not None:
                self._otel_host = m.group(1)
        else:
            self._otel_host = "localhost"

        self._otel_port = 13133

        super().__init__(
            image_name=image,
            name="collector",
            command="--config=/etc/otelcol-config.yml",
            environment={},
            volumes={self._otel_config_host_path: {"bind": "/etc/otelcol-config.yml", "mode": "ro"}},
            host_log_folder=host_log_folder,
            ports={"13133/tcp": ("0.0.0.0", 13133)},  # noqa: S104
        )

    # Override wait_for_health because we cannot do docker exec for container opentelemetry-collector-contrib
    def wait_for_health(self) -> bool:
        time.sleep(20)  # It takes long for otel collector to start

        for i in range(61):
            try:
                r = requests.get(f"http://{self._otel_host}:{self._otel_port}", timeout=1)
                logger.debug(f"Healthcheck #{i} on {self._otel_host}:{self._otel_port}: {r}")
                if r.status_code == HTTPStatus.OK:
                    return True
            except Exception as e:
                logger.debug(f"Healthcheck #{i} on {self._otel_host}:{self._otel_port}: {e}")
            time.sleep(1)

        logger.stdout(f"{self._otel_host}:{self._otel_port} never answered to healthcheck request")
        return False

    def start(self, network: Network) -> Container:
        # _otel_config_host_path is mounted in the container, and depending on umask,
        # it might have no read permissions for other users, which is required within
        # the container. So set them here.
        prev_mode = Path(self._otel_config_host_path).stat().st_mode
        new_mode = prev_mode | stat.S_IROTH
        if prev_mode != new_mode:
            Path(self._otel_config_host_path).chmod(new_mode)
        return super().start(network)


class APMTestAgentContainer(TestedContainer):
    def __init__(self, host_log_folder: str, agent_port: int = 8126) -> None:
        super().__init__(
            image_name="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.20.0",
            name="ddapm-test-agent",
            host_log_folder=host_log_folder,
            environment={
                "SNAPSHOT_CI": "0",
                "DD_APM_RECEIVER_SOCKET": "/var/run/datadog/apm.socket",
                "PORT": str(agent_port),
            },
            healthcheck={
                "test": f"curl --fail --silent --show-error http://localhost:{agent_port}/info",
                "retries": 60,
            },
            ports={agent_port: ("127.0.0.1", agent_port)},
            allow_old_container=False,
            volumes={f"./{host_log_folder}/interfaces/test_agent_socket": {"bind": "/var/run/datadog/", "mode": "rw"}},
        )


class MountInjectionVolume(TestedContainer):
    def __init__(self, host_log_folder: str, name: str) -> None:
        super().__init__(
            image_name="",
            name=name,
            host_log_folder=host_log_folder,
            command="/bin/true",
            volumes={_VOLUME_INJECTOR_NAME: {"bind": "/datadog-init/package", "mode": "rw"}},
        )

    def _lib_init_image(self, lib_init_image: str):
        self.image = ImageInfo(lib_init_image, local_image_only=False)
        # .NET compatible with former folder layer
        if "dd-lib-dotnet-init" in lib_init_image:
            self.volumes = {
                _VOLUME_INJECTOR_NAME: {"bind": "/datadog-init/monitoring-home", "mode": "rw"},
            }

    def remove(self):
        super().remove()
        _get_client().api.remove_volume(_VOLUME_INJECTOR_NAME)


class WeblogInjectionInitContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="docker.io/library/weblog-injection:latest",
            name="weblog-injection-init",
            host_log_folder=host_log_folder,
            ports={"18080": ("127.0.0.1", 8080)},
            allow_old_container=True,
            volumes={_VOLUME_INJECTOR_NAME: {"bind": "/datadog-lib", "mode": "rw"}},
        )

    def set_environment_for_library(self, library: ComponentVersion):
        lib_inject_props = {}
        for lang_env_vars in K8sWeblog.manual_injection_props["js" if library.name == "nodejs" else library.name]:
            lib_inject_props[lang_env_vars["name"]] = lang_env_vars["value"]
        lib_inject_props["DD_AGENT_HOST"] = "ddapm-test-agent"
        lib_inject_props["DD_TRACE_DEBUG"] = "true"
        self.environment = lib_inject_props


class DockerSSIContainer(TestedContainer):
    def __init__(self, host_log_folder: str, extra_env_vars: dict | None = None) -> None:
        environment = {
            "DD_DEBUG": "true",
            "DD_TRACE_DEBUG": "true",
            "DD_TRACE_SAMPLE_RATE": "1",
            "DD_TELEMETRY_METRICS_INTERVAL_SECONDS": "0.5",
            "DD_TELEMETRY_HEARTBEAT_INTERVAL": "0.5",
        }
        if extra_env_vars is not None:
            environment.update(extra_env_vars)
        super().__init__(
            image_name="docker.io/library/weblog-injection:latest",
            name="weblog-injection",
            host_log_folder=host_log_folder,
            ports={"18080": ("127.0.0.1", 18080), "8080": ("127.0.0.1", 8080), "9080": ("127.0.0.1", 9080)},
            healthcheck={"test": "sh /healthcheck.sh", "retries": 60},
            allow_old_container=False,
            environment=cast(dict[str, str | None], environment),
            volumes={f"./{host_log_folder}/interfaces/test_agent_socket": {"bind": "/var/run/datadog/", "mode": "rw"}},
        )

    def get_env(self, env_var: str):
        """Get env variables from the container"""
        env = (self.image.env or {}) | self.environment
        return env.get(env_var)


class DummyServerContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        super().__init__(
            image_name="jasonrm/dummy-server:latest",
            name="http-app",
            host_log_folder=host_log_folder,
            healthcheck={"test": "wget http://localhost:8080", "retries": 10},
        )


class EnvoyContainer(TestedContainer):
    def __init__(self, host_log_folder: str) -> None:
        from utils import weblog

        super().__init__(
            image_name="envoyproxy/envoy:v1.31-latest",
            name="envoy",
            host_log_folder=host_log_folder,
            volumes={"./tests/external_processing/envoy.yaml": {"bind": "/etc/envoy/envoy.yaml", "mode": "ro"}},
            ports={"80": ("127.0.0.1", weblog.port)},
            healthcheck={
                "test": "/bin/bash -c \"\
                    exec 3<>/dev/tcp/127.0.0.1/80 || exit 1;\
                    echo -e 'GET / HTTP/1.1\nHost: system-tests\r\n\r\n' >&3;\
                    cat <&3 | grep -q '200'\"",
                "retries": 10,
            },
        )


class ExternalProcessingContainer(TestedContainer):
    library: ComponentVersion

    def __init__(
        self,
        host_log_folder: str,
        env: dict[str, str | None] | None,
        volumes: dict[str, dict[str, str]] | None,
    ) -> None:
        try:
            with open("binaries/golang-service-extensions-callout-image", encoding="utf-8") as f:
                image = f.read().strip()
        except FileNotFoundError:
            image = "ghcr.io/datadog/dd-trace-go/service-extensions-callout:latest"

        environment: dict[str, str | None] = {
            "DD_APPSEC_ENABLED": "true",
            "DD_SERVICE": "service_test",
            "DD_AGENT_HOST": "proxy",
            "DD_TRACE_AGENT_PORT": str(ProxyPorts.weblog),
            "DD_APPSEC_WAF_TIMEOUT": "1s",
        }

        if env:
            environment.update(env)

        if volumes is None:
            volumes = {}

        super().__init__(
            image_name=image,
            name="extproc",
            host_log_folder=host_log_folder,
            volumes=volumes,
            environment=environment,
            healthcheck={
                "test": "wget -qO- http://localhost:80/",
                "retries": 10,
            },
        )

    def post_start(self):
        with open(self.healthcheck_log_file, encoding="utf-8") as f:
            data = json.load(f)
            lib = data["library"]

        if "language" in lib:
            self.library = ComponentVersion(lib["language"], lib["version"])
        else:
            self.library = ComponentVersion(lib["name"], lib["version"])

        logger.stdout(f"Library: {self.library}")
        logger.stdout(f"Image: {self.image.name}")
