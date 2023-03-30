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
    def __init__(self, name, image_name, allow_old_container=False, healthcheck=None, **kwargs) -> None:
        self.name = name
        self.container_name = f"system-tests-{name}"
        self.image_name = image_name
        self.allow_old_container = allow_old_container
        self.healthcheck = healthcheck

        self.kwargs = kwargs
        self._container = None

    @property
    def log_folder_path(self):
        return f"/app/logs/docker/{self.name}"

    def get_existing_container(self) -> Container:
        for container in _client.containers.list(all=True, filters={"name": self.container_name}):
            if container.name == self.container_name:
                logger.debug(f"Container {self.container_name} found")
                return container

    def start(self) -> Container:
        Path(self.log_folder_path).mkdir(exist_ok=True)

        if old_container := self.get_existing_container():
            if self.allow_old_container:
                self._container = old_container
                logger.debug(f"Use old container {self.container_name}")
                return

            logger.debug(f"Kill old container {self.container_name}")
            old_container.remove(force=True)

        self._fix_host_pwd_in_volumes()

        logger.info(f"Start container {self.container_name}")

        self._container = _client.containers.run(
            image=self.image_name,
            name=self.container_name,
            # auto_remove=True,
            detach=True,
            hostname=self.name,
            network="system-tests_default",
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

        host_pwd = os.environ["HOST_PWD"]

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

    def __init__(self, image_name):
        self.env = {}

        try:
            with open(f"logs/{image_name}_image.json", encoding="ascii") as fp:
                self._raw = json.load(fp)
        except FileNotFoundError:
            return  # silently fail, needed for testing

        for var in self._raw[0]["Config"]["Env"]:
            key, value = var.split("=", 1)
            self.env[key] = value


class AgentContainer(TestedContainer):
    def __init__(self) -> None:
        super().__init__(
            image_name="system_tests/agent",
            name="agent",
            environment={
                "DD_API_KEY": os.environ.get("DD_API_KEY", "please-set-DD_API_KEY"),
                "DD_ENV": "system-tests",
                "DD_HOSTNAME": "test",
                "DD_SITE": self.dd_site,
                "DD_APM_RECEIVER_PORT": self.agent_port,
                "DD_DOGSTATSD_PORT": "8125",  # TODO : move this in agent build ?
            },
            healthcheck=_HealthCheck(f"http://agent:{self.agent_port}/info", 60, start_period=1),
        )

        self.image_info = ImageInfo("agent")

        agent_version = self.image_info.env.get("SYSTEM_TESTS_AGENT_VERSION")

        if not agent_version:
            self.agent_version = None
        else:
            self.agent_version = Version(agent_version, "agent")

    @property
    def dd_site(self):
        return os.environ.get("DD_SITE", "datad0g.com")

    @property
    def agent_port(self):
        return 8126


class WeblogContainer(TestedContainer):
    def __init__(
        self,
        host_log_folder,
        environment=None,
        tracer_sampling_rate=None,
        appsec_rules=None,
        appsec_enabled=True,
        additional_trace_header_tags=(),
    ) -> None:

        self.image_info = ImageInfo("weblog")

        self.tracer_sampling_rate = tracer_sampling_rate

        self.uds_socket = self.image_info.env.get("DD_APM_RECEIVER_SOCKET", None)

        self.library = LibraryVersion(
            self.image_info.env.get("SYSTEM_TESTS_LIBRARY", None),
            self.image_info.env.get("SYSTEM_TESTS_LIBRARY_VERSION", None),
        )

        self.weblog_variant = self.image_info.env.get("SYSTEM_TESTS_WEBLOG_VARIANT", None)

        if self.library == "php":
            self.php_appsec = Version(self.image_info.env.get("SYSTEM_TESTS_PHP_APPSEC_VERSION"), "php_appsec")
        else:
            self.php_appsec = None

        libddwaf_version = self.image_info.env.get("SYSTEM_TESTS_LIBDDWAF_VERSION", None)

        if not libddwaf_version:
            self.libddwaf_version = None
        else:
            self.libddwaf_version = Version(libddwaf_version, "libddwaf")

        appsec_rules_version = self.image_info.env.get("SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION", "0.0.0")
        self.appsec_rules_version = Version(appsec_rules_version, "appsec_rules")

        # Basic env set for all scenarios
        base_environment = {}

        base_environment["DD_TELEMETRY_HEARTBEAT_INTERVAL"] = self.telemetry_heartbeat_interval

        if appsec_enabled:
            base_environment["DD_APPSEC_ENABLED"] = "true"

        if self.library in ("cpp", "dotnet", "java", "python"):
            base_environment["DD_TRACE_HEADER_TAGS"] = "user-agent:http.request.headers.user-agent"
        elif self.library in ("golang", "nodejs", "php", "ruby"):
            base_environment["DD_TRACE_HEADER_TAGS"] = "user-agent"
        else:
            base_environment["DD_TRACE_HEADER_TAGS"] = ""

        if len(additional_trace_header_tags) != 0:
            base_environment["DD_TRACE_HEADER_TAGS"] += ",".join(additional_trace_header_tags)

        if tracer_sampling_rate:
            base_environment["DD_TRACE_SAMPLE_RATE"] = str(tracer_sampling_rate)

        if appsec_rules:
            base_environment["DD_APPSEC_RULES"] = str(appsec_rules)
            self.appsec_rules_file = str(appsec_rules)
        else:
            self.appsec_rules_file = self.image_info.env.get("DD_APPSEC_RULES", None)

        # set the tracer to send data to runner (it will forward them to the agent)
        base_environment["DD_AGENT_HOST"] = "runner"
        base_environment["DD_TRACE_AGENT_PORT"] = 8126

        environment = base_environment | (environment or {})

        super().__init__(
            image_name="system_tests/weblog",
            name="weblog",
            environment=environment,
            volumes={f"./{host_log_folder}/docker/weblog/logs/": {"bind": "/var/log/system-tests", "mode": "rw"},},
            # ddprof's perf event open is blocked by default by docker's seccomp profile
            # This is worse than the line above though prevents mmap bugs locally
            security_opt=["seccomp=unconfined"],
            healthcheck=_HealthCheck("http://weblog:7777", 60),
        )

    @property
    def environment(self):
        return self.kwargs["environment"]

    @property
    def uds_mode(self):
        return self.uds_socket is not None

    @property
    def telemetry_heartbeat_interval(self):
        return 2
