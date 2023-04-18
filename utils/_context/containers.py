import os
import json
from pathlib import Path
import time
import docker
from docker.models.containers import Container
import pytest
import requests

from utils._context.library_version import LibraryVersion, Version
from utils.tools import logger

_client = docker.DockerClient()

_NETWORK_NAME = "system-tests_default"


def create_network():
    for _ in _client.networks.list(names=[_NETWORK_NAME,]):
        logger.debug(f"Network {_NETWORK_NAME} still exists")
        return

    logger.debug(f"Create network {_NETWORK_NAME}")
    _client.networks.create(_NETWORK_NAME, check_duplicate=True)


class _HealthCheck:
    def __init__(self, url, retries, interval=1, start_period=0):
        self.url = url
        self.retries = retries
        self.interval = interval
        self.start_period = start_period

    def __call__(self):
        if self.start_period:
            time.sleep(self.start_period)

        for i in range(self.retries + 1):
            try:
                r = requests.get(self.url, timeout=1)
                logger.debug(f"Healthcheck #{i} on {self.url}: {r}")
                if r.status_code == 200:
                    return
            except Exception as e:
                logger.debug(f"Healthcheck #{i} on {self.url}: {e}")

            time.sleep(self.interval)

        pytest.exit(f"{self.url} never answered to healthcheck request", 1)

    def __str__(self):
        return (
            f"Healthcheck({repr(self.url)}, retries={self.retries}, "
            f"interval={self.interval}, start_period={self.start_period})"
        )


class TestedContainer:

    # https://docker-py.readthedocs.io/en/stable/containers.html
    def __init__(
        self, name, image_name, host_log_folder, environment=None, allow_old_container=False, healthcheck=None, **kwargs
    ) -> None:
        self.name = name
        self.host_log_folder = host_log_folder

        Path(self.log_folder_path).mkdir(exist_ok=True, parents=True)
        Path(f"{self.log_folder_path}/logs").mkdir(exist_ok=True, parents=True)

        self.image = ImageInfo(image_name, dir_path=self.log_folder_path)
        self.allow_old_container = allow_old_container
        self.healthcheck = healthcheck
        self.environment = self.image.env | (environment or {})

        self.kwargs = kwargs
        self._container = None

    @property
    def container_name(self):
        return f"system-tests-{self.name}"

    @property
    def log_folder_path(self):
        return f"./{self.host_log_folder}/docker/{self.name}"

    def get_existing_container(self) -> Container:
        for container in _client.containers.list(all=True, filters={"name": self.container_name}):
            if container.name == self.container_name:
                logger.debug(f"Container {self.container_name} found")
                return container

    def stop_previous_container(self):
        if self.allow_old_container:
            return

        if old_container := self.get_existing_container():
            logger.debug(f"Kill old container {self.container_name}")
            old_container.remove(force=True)

    def start(self) -> Container:
        if old_container := self.get_existing_container():
            if self.allow_old_container:
                self._container = old_container
                logger.debug(f"Use old container {self.container_name}")
                return

            raise ValueError("Old container still exists")

        self._fix_host_pwd_in_volumes()

        logger.info(f"Start container {self.container_name}")

        self._container = _client.containers.run(
            image=self.image.name,
            name=self.container_name,
            hostname=self.name,
            environment=self.environment,
            # auto_remove=True,
            detach=True,
            network=_NETWORK_NAME,
            **self.kwargs,
        )

        if self.healthcheck:
            self.healthcheck()

    def _fix_host_pwd_in_volumes(self):
        # on docker compose, volume host path can starts with a "."
        # it means the current path on host machine. It's not supported in bare docker
        # replicate this behavior here
        if "volumes" not in self.kwargs:
            return

        host_pwd = os.getcwd()

        result = {}
        for k, v in self.kwargs["volumes"].items():
            if k.startswith("./"):
                k = f"{host_pwd}{k[1:]}"
            result[k] = v

        self.kwargs["volumes"] = result

    def save_logs(self):
        if not self._container:
            return

        with open(f"{self.log_folder_path}/stdout.log", "wb") as f:
            f.write(self._container.logs(stdout=True, stderr=False))

        with open(f"{self.log_folder_path}/stderr.log", "wb") as f:
            f.write(self._container.logs(stdout=False, stderr=True))

    def remove(self):

        if not self._container:
            return

        try:
            self._container.remove(force=True)
        except:
            # Sometimes, the container does not exists.
            # We can safely ignore this, because if it's another issue
            # it will be killed at startup

            pass


class ImageInfo:
    """data on docker image. data comes from `docker inspect`"""

    def __init__(self, image_name, dir_path):
        self.env = {}
        self.name = image_name
        try:
            self._image = _client.images.get(image_name)
        except docker.errors.ImageNotFound:
            logger.info(f"Image {image_name} has not been found locally")
            self._image = _client.images.pull(image_name)

        for var in self._image.attrs["Config"]["Env"]:
            key, value = var.split("=", 1)
            self.env[key] = value

        with open(f"{dir_path}/image.json", encoding="utf-8", mode="w") as f:
            json.dump(self._image.attrs, f, indent=2)


class AgentContainer(TestedContainer):
    def __init__(self, host_log_folder, use_proxy=True) -> None:

        if "DD_API_KEY" not in os.environ:
            raise ValueError("DD_API_KEY is missing in env, please add it.")

        environment = {
            "DD_API_KEY": os.environ["DD_API_KEY"],
            "DD_ENV": "system-tests",
            "DD_HOSTNAME": "test",
            "DD_SITE": self.dd_site,
            "DD_APM_RECEIVER_PORT": self.agent_port,
            "DD_DOGSTATSD_PORT": "8125",
        }

        if use_proxy:
            environment["DD_PROXY_HTTPS"] = "http://proxy:8126"
            environment["DD_PROXY_HTTP"] = "http://proxy:8126"

        super().__init__(
            image_name="system_tests/agent",
            name="agent",
            host_log_folder=host_log_folder,
            environment=environment,
            healthcheck=_HealthCheck(f"http://localhost:{self.agent_port}/info", 60, start_period=1),
            ports={f"{self.agent_port}/tcp": ("127.0.0.1", self.agent_port)},
        )

        agent_version = self.image.env.get("SYSTEM_TESTS_AGENT_VERSION")

        if not agent_version:
            self.agent_version = None
        else:
            self.agent_version = Version(agent_version, "agent")

    @property
    def dd_site(self):
        return os.environ.get("DD_SITE", "datad0g.com")

    @property
    def agent_port(self):
        return 8127


class WeblogContainer(TestedContainer):
    def __init__(
        self,
        host_log_folder,
        environment=None,
        tracer_sampling_rate=None,
        appsec_rules=None,
        appsec_enabled=True,
        additional_trace_header_tags=(),
        use_proxy=True,
    ) -> None:

        super().__init__(
            image_name="system_tests/weblog",
            name="weblog",
            host_log_folder=host_log_folder,
            environment=environment or {},
            volumes={f"./{host_log_folder}/docker/weblog/logs/": {"bind": "/var/log/system-tests", "mode": "rw"},},
            # ddprof's perf event open is blocked by default by docker's seccomp profile
            # This is worse than the line above though prevents mmap bugs locally
            security_opt=["seccomp=unconfined"],
            healthcheck=_HealthCheck("http://localhost:7777", 60),
            ports={"7777/tcp": ("127.0.0.1", 7777), "7778/tcp": ("127.0.0.1", 7778)},
        )

        self.tracer_sampling_rate = tracer_sampling_rate

        self.weblog_variant = self.image.env.get("SYSTEM_TESTS_WEBLOG_VARIANT", None)

        if self.library == "php":
            self.php_appsec = Version(self.image.env.get("SYSTEM_TESTS_PHP_APPSEC_VERSION"), "php_appsec")
        else:
            self.php_appsec = None

        libddwaf_version = self.image.env.get("SYSTEM_TESTS_LIBDDWAF_VERSION", None)

        if not libddwaf_version:
            self.libddwaf_version = None
        else:
            self.libddwaf_version = Version(libddwaf_version, "libddwaf")

        appsec_rules_version = self.image.env.get("SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION", "0.0.0")
        self.appsec_rules_version = Version(appsec_rules_version, "appsec_rules")

        # Basic env set for all scenarios
        self.environment["DD_TELEMETRY_HEARTBEAT_INTERVAL"] = self.telemetry_heartbeat_interval

        if appsec_enabled:
            self.environment["DD_APPSEC_ENABLED"] = "true"

        if self.library in ("cpp", "dotnet", "java", "python"):
            self.environment["DD_TRACE_HEADER_TAGS"] = "user-agent:http.request.headers.user-agent"
        elif self.library in ("golang", "nodejs", "php", "ruby"):
            self.environment["DD_TRACE_HEADER_TAGS"] = "user-agent"
        else:
            self.environment["DD_TRACE_HEADER_TAGS"] = ""

        if len(additional_trace_header_tags) != 0:
            self.environment["DD_TRACE_HEADER_TAGS"] += ",".join(additional_trace_header_tags)

        if tracer_sampling_rate:
            self.environment["DD_TRACE_SAMPLE_RATE"] = str(tracer_sampling_rate)

        if appsec_rules:
            self.environment["DD_APPSEC_RULES"] = str(appsec_rules)
            self.appsec_rules_file = str(appsec_rules)
        else:
            self.appsec_rules_file = self.image.env.get("DD_APPSEC_RULES", None)

        if use_proxy:
            # set the tracer to send data to runner (it will forward them to the agent)
            self.environment["DD_AGENT_HOST"] = "proxy"
            self.environment["DD_TRACE_AGENT_PORT"] = 8126
        else:
            self.environment["DD_AGENT_HOST"] = "agent"
            self.environment["DD_TRACE_AGENT_PORT"] = 8127

    @property
    def library(self):
        return LibraryVersion(
            self.image.env.get("SYSTEM_TESTS_LIBRARY", None), self.image.env.get("SYSTEM_TESTS_LIBRARY_VERSION", None),
        )

    @property
    def uds_socket(self):
        return self.image.env.get("DD_APM_RECEIVER_SOCKET", None)

    @property
    def uds_mode(self):
        return self.uds_socket is not None

    @property
    def telemetry_heartbeat_interval(self):
        return 2
