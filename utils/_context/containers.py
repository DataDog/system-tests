import os
import re
import stat
import json
from pathlib import Path
from subprocess import run
import time
from functools import lru_cache
import platform
from threading import RLock, Thread

import docker
from docker.errors import APIError, DockerException
from docker.models.containers import Container
import pytest
import requests

from utils._context.library_version import LibraryVersion
from utils.tools import logger
from utils import interfaces
from utils.k8s_lib_injection.k8s_weblog import K8sWeblog


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
            pass

        raise e


_NETWORK_NAME = "system-tests_default"


def create_network():
    for _ in _get_client().networks.list(names=[_NETWORK_NAME,]):
        logger.debug(f"Network {_NETWORK_NAME} still exists")
        return

    logger.debug(f"Create network {_NETWORK_NAME}")
    _get_client().networks.create(_NETWORK_NAME, check_duplicate=True)


_VOLUME_INJECTOR_NAME = "volume-inject"


def create_inject_volume():

    logger.debug(f"Create volume {_VOLUME_INJECTOR_NAME}")
    _get_client().volumes.create(_VOLUME_INJECTOR_NAME)


class TestedContainer:

    # https://docker-py.readthedocs.io/en/stable/containers.html
    def __init__(
        self,
        name,
        image_name,
        host_log_folder,
        environment=None,
        allow_old_container=False,
        healthcheck=None,
        stdout_interface=None,
        **kwargs,
    ) -> None:
        self.name = name
        self.host_project_dir = os.environ.get("SYSTEM_TESTS_HOST_PROJECT_DIR", os.getcwd())
        self.host_log_folder = host_log_folder
        self.allow_old_container = allow_old_container

        self.image = ImageInfo(image_name)
        self.healthcheck = healthcheck

        # healthy values:
        # None: container did not tried to start yet, or hasn't be started for another reason
        # False: container is not healthy
        # True: container is healthy
        self.healthy = None

        self.environment = environment or {}
        self.kwargs = kwargs
        self._container = None
        self.depends_on: list[TestedContainer] = []
        self._starting_lock = RLock()
        self._starting_thread = None
        self.stdout_interface = stdout_interface

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        """ returns the image list that will be loaded to be able to run/build the container """
        return [self.image.name]

    def configure(self, replay):

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

    def stop_previous_container(self):
        if self.allow_old_container:
            return

        if old_container := self.get_existing_container():
            logger.debug(f"Kill old container {self.container_name}")
            old_container.remove(force=True)

    def start(self) -> Container:
        """ Start the actual underlying Docker container directly """
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
            network=_NETWORK_NAME,
            **self.kwargs,
        )

        self.healthy = self.wait_for_health()
        if self.healthy:
            self.warmup()

    def async_start(self) -> Thread:
        """ Start the container and its dependencies in a thread with circular dependency detection """
        self.check_circular_dependencies([])

        return self._async_start_recursive()

    def check_circular_dependencies(self, seen: list):
        """ Check if the container has a circular dependency """
        if self in seen:
            dependencies = " -> ".join([s.name for s in seen] + [self.name,])
            raise RuntimeError(f"Circular dependency detected between containers: {dependencies}")

        seen.append(self)

        for dependency in self.depends_on:
            dependency.check_circular_dependencies(list(seen))

    def _async_start_recursive(self):
        """ Recursive version of async_start for circular dependency detection """
        with self._starting_lock:
            if self._starting_thread is None:
                self._starting_thread = Thread(target=self._start_with_dependencies, name=f"start_{self.name}")
                self._starting_thread.start()

        return self._starting_thread

    def _start_with_dependencies(self):
        """ Start all dependencies of a container and then start the container """
        threads = [dependency._async_start_recursive() for dependency in self.depends_on]

        for thread in threads:
            thread.join()

        for dependency in self.depends_on:
            if not dependency.healthy:
                return

        # this function is executed in a thread
        # the main thread will take care of the exception
        try:
            self.start()
        except Exception as e:
            logger.exception(f"Error while starting {self.name}: {e}")
            self.healthy = False

    def warmup(self):
        """ if some stuff must be done after healthcheck """

    def post_start(self):
        """ if some stuff must be done after the container is started """

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

        return True

    def execute_command(
        self, test, retries=10, interval=1_000_000_000, start_period=0, timeout=1_000_000_000
    ) -> tuple[int, str]:
        """
            Execute a command inside a container. Usefull for healthcheck and warmups.
            test is a command to be executed, interval, timeout and start_period are in us (microseconds)
            This function does not raise any exception, it returns a tuple with the exit code and the output
            The exit code is 0 (success) or any other integer (failure)
        """

        cmd = test

        if not isinstance(cmd, str):
            assert cmd[0] == "CMD-SHELL", "Only CMD-SHELL is supported"
            cmd = cmd[1]

        interval = interval / 1_000_000_000
        # timeout = timeout / 1_000_000_000
        start_period = start_period / 1_000_000_000

        if start_period:
            time.sleep(start_period)

        logger.info(f"Executing command {cmd} for {self.name}")

        result = None

        for i in range(retries + 1):
            try:
                result = self._container.exec_run(cmd)

                logger.debug(f"Try #{i}: {result}")

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
        if "volumes" not in self.kwargs:
            return

        host_pwd = self.host_project_dir

        result = {}
        for k, v in self.kwargs["volumes"].items():
            if k.startswith("./"):
                k = f"{host_pwd}{k[1:]}"
            result[k] = v

        self.kwargs["volumes"] = result

    def stop(self):
        if self._container:
            self._container.stop()
        self._starting_thread = None

    def collect_logs(self):
        stdout = self._container.logs(stdout=True, stderr=False)
        stderr = self._container.logs(stdout=False, stderr=True)

        with open(f"{self.log_folder_path}/stdout.log", "wb") as f:
            f.write(stdout)

        with open(f"{self.log_folder_path}/stderr.log", "wb") as f:
            f.write(stderr)

        if not self.healthy:
            sep = "=" * 30
            logger.stdout(f"\n{sep} {self.name} STDERR {sep}")
            logger.stdout(stderr.decode("utf-8"))
            logger.stdout(f"\n{sep} {self.name} STDOUT {sep}")
            logger.stdout(stdout.decode("utf-8"))
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

                pass

        if self.stdout_interface is not None:
            self.stdout_interface.load_data()


class SqlDbTestedContainer(TestedContainer):
    def __init__(
        self,
        name,
        image_name,
        host_log_folder,
        environment=None,
        allow_old_container=False,
        healthcheck=None,
        stdout_interface=None,
        ports=None,
        db_user=None,
        db_password=None,
        db_instance=None,
        db_host=None,
        dd_integration_service=None,
        **kwargs,
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
            **kwargs,
        )
        self.dd_integration_service = dd_integration_service
        self.db_user = db_user
        self.db_password = db_password
        self.db_host = db_host
        self.db_instance = db_instance


class ImageInfo:
    """data on docker image. data comes from `docker inspect`"""

    def __init__(self, image_name):
        self.env = None
        self.name = image_name

    def load(self):
        try:
            self._image = _get_client().images.get(self.name)
        except docker.errors.ImageNotFound:
            logger.stdout(f"Pulling {self.name}")
            self._image = _get_client().images.pull(self.name)

        self._init_from_attrs(self._image.attrs)

    def load_from_logs(self, dir_path):
        with open(f"{dir_path}/image.json", encoding="utf-8", mode="r") as f:
            attrs = json.load(f)

        self._init_from_attrs(attrs)

    def _init_from_attrs(self, attrs):
        self.env = {}

        for var in attrs["Config"]["Env"]:
            key, value = var.split("=", 1)
            if value:
                self.env[key] = value

    def save_image_info(self, dir_path):
        with open(f"{dir_path}/image.json", encoding="utf-8", mode="w") as f:
            json.dump(self._image.attrs, f, indent=2)


class ProxyContainer(TestedContainer):
    def __init__(self, host_log_folder, rc_api_enabled: bool, meta_structs_disabled: bool) -> None:

        super().__init__(
            image_name="datadog/system-tests:proxy-v1",
            name="proxy",
            host_log_folder=host_log_folder,
            environment={
                "DD_SITE": os.environ.get("DD_SITE"),
                "DD_API_KEY": os.environ.get("DD_API_KEY"),
                "DD_APP_KEY": os.environ.get("DD_APP_KEY"),
                "SYSTEM_TESTS_HOST_LOG_FOLDER": host_log_folder,
                "SYSTEM_TESTS_RC_API_ENABLED": str(rc_api_enabled),
                "SYSTEM_TESTS_AGENT_SPAN_META_STRUCTS_DISABLED": str(meta_structs_disabled),
            },
            working_dir="/app",
            volumes={
                f"./{host_log_folder}/interfaces/": {"bind": f"/app/{host_log_folder}/interfaces", "mode": "rw",},
                "./utils/": {"bind": "/app/utils/", "mode": "ro"},
            },
            ports={"11111/tcp": ("127.0.0.1", 11111)},
            command="python utils/proxy/core.py",
        )


class AgentContainer(TestedContainer):
    def __init__(self, host_log_folder, use_proxy=True) -> None:

        environment = {
            "DD_ENV": "system-tests",
            "DD_HOSTNAME": "test",
            "DD_SITE": self.dd_site,
            "DD_APM_RECEIVER_PORT": self.agent_port,
            "DD_DOGSTATSD_PORT": "8125",
            "SOME_SECRET_ENV": "leaked-env-var",  # used for test that env var are not leaked
        }

        if use_proxy:
            environment["DD_PROXY_HTTPS"] = "http://proxy:8126"
            environment["DD_PROXY_HTTP"] = "http://proxy:8126"

        super().__init__(
            image_name="system_tests/agent",
            name="agent",
            host_log_folder=host_log_folder,
            environment=environment,
            healthcheck={
                "test": f"curl --fail --silent --show-error http://localhost:{self.agent_port}/info",
                "retries": 60,
            },
            ports={self.agent_port: f"{self.agent_port}/tcp"},
            stdout_interface=interfaces.agent_stdout,
        )

        self.agent_version = None

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        try:
            with open("binaries/agent-image", "r", encoding="utf-8") as f:
                return [
                    f.read().strip(),
                ]
        except FileNotFoundError:
            # not the cleanest way to do it, but we save ARG parsing
            return [
                "datadog/agent:latest",
            ]

    def configure(self, replay):
        super().configure(replay)

        if "DD_API_KEY" not in os.environ:
            raise ValueError("DD_API_KEY is missing in env, please add it.")

        self.environment["DD_API_KEY"] = os.environ["DD_API_KEY"]

    def post_start(self):
        with open(self.healthcheck_log_file, mode="r", encoding="utf-8") as f:
            data = json.load(f)

        self.agent_version = LibraryVersion("agent", data["version"]).version

        logger.stdout(f"Agent: {self.agent_version}")
        logger.stdout(f"Backend: {self.dd_site}")

    @property
    def dd_site(self):
        return os.environ.get("DD_SITE", "datad0g.com")

    @property
    def agent_port(self):
        return 8127


class BuddyContainer(TestedContainer):
    def __init__(self, name, image_name, host_log_folder, proxy_port, environment) -> None:
        super().__init__(
            name=name,
            image_name=image_name,
            host_log_folder=host_log_folder,
            healthcheck={"test": "curl --fail --silent --show-error localhost:7777", "retries": 60},
            ports={"7777/tcp": proxy_port},  # not the proxy port
            environment={
                **environment,
                "DD_SERVICE": name,
                "DD_ENV": "system-tests",
                "DD_VERSION": "1.0.0",
                # "DD_TRACE_DEBUG": "true",
                "DD_AGENT_HOST": "proxy",
                "DD_TRACE_AGENT_PORT": proxy_port,
            },
        )

        # try:
        #     assert "AWS_ACCESS_KEY_ID" in os.environ, os.environ
        # except AssertionError as e:
        #     print(e)
        #     pass

        self.interface = None
        self.environment["AWS_ACCESS_KEY_ID"] = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self.environment["AWS_SECRET_ACCESS_KEY"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self.environment["AWS_DEFAULT_REGION"] = os.environ.get("AWS_DEFAULT_REGION", "")
        self.environment["AWS_REGION"] = os.environ.get("AWS_REGION", "")


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

        from utils import weblog

        self.port = weblog.port

        super().__init__(
            image_name="system_tests/weblog",
            name="weblog",
            host_log_folder=host_log_folder,
            environment=environment or {},
            volumes={f"./{host_log_folder}/docker/weblog/logs/": {"bind": "/var/log/system-tests", "mode": "rw",},},
            # ddprof's perf event open is blocked by default by docker's seccomp profile
            # This is worse than the line above though prevents mmap bugs locally
            security_opt=["seccomp=unconfined"],
            healthcheck={"test": f"curl --fail --silent --show-error localhost:{self.port}", "retries": 60},
            ports={"7777/tcp": self.port, "7778/tcp": weblog._grpc_port},
            stdout_interface=interfaces.library_stdout,
        )

        self.tracer_sampling_rate = tracer_sampling_rate
        self.appsec_rules_file = appsec_rules
        self.additional_trace_header_tags = additional_trace_header_tags

        self.weblog_variant = ""
        self.libddwaf_version = None
        self.appsec_rules_version = None
        self._library: LibraryVersion = None

        # Basic env set for all scenarios
        self.environment["DD_TELEMETRY_HEARTBEAT_INTERVAL"] = self.telemetry_heartbeat_interval

        if appsec_enabled:
            self.environment["DD_APPSEC_ENABLED"] = "true"

        if tracer_sampling_rate:
            self.environment["DD_TRACE_SAMPLE_RATE"] = str(tracer_sampling_rate)

        if use_proxy:
            # set the tracer to send data to runner (it will forward them to the agent)
            self.environment["DD_AGENT_HOST"] = "proxy"
            self.environment["DD_TRACE_AGENT_PORT"] = 8126
        else:
            self.environment["DD_AGENT_HOST"] = "agent"
            self.environment["DD_TRACE_AGENT_PORT"] = 8127

    @staticmethod
    def _get_image_list_from_dockerfile(dockerfile) -> list[str]:
        result = []

        pattern = re.compile(r"FROM\s+(?P<image_name>[^ ]+)")
        with open(dockerfile, "r", encoding="utf-8") as f:
            for line in f.readlines():
                if match := pattern.match(line):
                    result.append(match.group("image_name"))

        return result

    def get_image_list(self, library: str, weblog: str) -> list[str]:
        """ parse the Dockerfile and extract all images reference in a FROM section """
        result = []
        args = {}

        pattern = re.compile(r"^FROM\s+(?P<image_name>[^\s]+)")
        arg_pattern = re.compile(r"^ARG\s+(?P<arg_name>[^\s]+)\s*=\s*(?P<arg_value>[^\s]+)")
        with open(f"utils/build/docker/{library}/{weblog}.Dockerfile", "r", encoding="utf-8") as f:
            for line in f.readlines():
                if match := arg_pattern.match(line):
                    args[match.group("arg_name")] = match.group("arg_value")

                if match := pattern.match(line):
                    image_name = match.group("image_name")

                    for name, value in args.items():
                        image_name = image_name.replace(f"${name}", value)

                    result.append(image_name)

        return result

    def configure(self, replay):
        super().configure(replay)

        # try:
        #     assert "AWS_ACCESS_KEY_ID" in os.environ, os.environ
        # except AssertionError as e:
        #     print(e)
        #     pass

        self.weblog_variant = self.image.env.get("SYSTEM_TESTS_WEBLOG_VARIANT", None)

        if libddwaf_version := self.image.env.get("SYSTEM_TESTS_LIBDDWAF_VERSION", None):
            self.libddwaf_version = LibraryVersion("libddwaf", libddwaf_version).version

        appsec_rules_version = self.image.env.get("SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION", "0.0.0")
        self.appsec_rules_version = LibraryVersion("appsec_rules", appsec_rules_version).version

        self.environment["AWS_ACCESS_KEY_ID"] = os.environ.get("AWS_ACCESS_KEY_ID", "")
        self.environment["AWS_SECRET_ACCESS_KEY"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self.environment["AWS_DEFAULT_REGION"] = os.environ.get("AWS_DEFAULT_REGION", "")
        self.environment["AWS_REGION"] = os.environ.get("AWS_REGION", "")

        self._library = LibraryVersion(
            self.image.env.get("SYSTEM_TESTS_LIBRARY", None), self.image.env.get("SYSTEM_TESTS_LIBRARY_VERSION", None),
        )

        # https://github.com/DataDog/system-tests/issues/2799
        if self.library in ("nodejs",):
            self.healthcheck = {
                "test": f"curl --fail --silent --show-error localhost:{self.port}/healthcheck",
                "retries": 60,
            }

        if self.library in ("cpp", "dotnet", "java", "python"):
            self.environment["DD_TRACE_HEADER_TAGS"] = "user-agent:http.request.headers.user-agent"

            if self.library == "python":
                # activating debug log on python causes a huge amount of logs, making the network
                # stack fails a lot randomly
                self.environment["DD_TRACE_DEBUG"] = "false"

        elif self.library in ("golang", "nodejs", "php", "ruby"):
            self.environment["DD_TRACE_HEADER_TAGS"] = "user-agent"
        else:
            self.environment["DD_TRACE_HEADER_TAGS"] = ""

        if len(self.additional_trace_header_tags) != 0:
            self.environment["DD_TRACE_HEADER_TAGS"] += f',{",".join(self.additional_trace_header_tags)}'

        if self.appsec_rules_file:
            self.environment["DD_APPSEC_RULES"] = self.appsec_rules_file
        else:
            self.appsec_rules_file = (self.image.env | self.environment).get("DD_APPSEC_RULES", None)

        if self.weblog_variant == "python3.12":
            if self.library < "python@2.1.0.dev":  # profiling causes a seg fault on 2.0.0
                self.environment["DD_PROFILING_ENABLED"] = "false"

    def post_start(self):
        from utils import weblog

        logger.debug(f"Docker host is {weblog.domain}")

        # new way of getting info from the weblog. Only working for nodejs right now
        # https://github.com/DataDog/system-tests/issues/2799
        if self.library == "nodejs":
            with open(self.healthcheck_log_file, mode="r", encoding="utf-8") as f:
                data = json.load(f)

            self._library = LibraryVersion(data["library"]["language"], data["library"]["version"])
            self.libddwaf_version = LibraryVersion("libddwaf", data["library"]["libddwaf_version"]).version

        logger.stdout(f"Library: {self.library}")

        if self.libddwaf_version:
            logger.stdout(f"libddwaf: {self.libddwaf_version}")

        if self.appsec_rules_file:
            logger.stdout(f"AppSec rules version: {self.appsec_rules_version}")

        if self.uds_mode:
            logger.stdout(f"UDS socket: {self.uds_socket}")

        logger.stdout(f"Weblog variant: {self.weblog_variant}")

        self.stdout_interface.init_patterns(self.library)

    @property
    def library(self) -> LibraryVersion:
        return self._library

    @property
    def uds_socket(self):
        return self.image.env.get("DD_APM_RECEIVER_SOCKET", None)

    @property
    def uds_mode(self):
        return self.uds_socket is not None

    @property
    def telemetry_heartbeat_interval(self):
        return 2

    def request(self, method, url, **kwargs):
        """ perform an HTTP request on the weblog, must NOT be used for tests """
        return requests.request(method, f"http://localhost:{self.port}{url}", **kwargs)


class PostgresContainer(SqlDbTestedContainer):
    def __init__(self, host_log_folder) -> None:
        super().__init__(
            image_name="postgres:alpine",
            name="postgres",
            host_log_folder=host_log_folder,
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
            db_password="system_tests",
            db_host="postgres",
            db_instance="system_tests_dbname",
        )


class MongoContainer(TestedContainer):
    def __init__(self, host_log_folder) -> None:
        super().__init__(
            image_name="mongo:latest", name="mongodb", host_log_folder=host_log_folder, allow_old_container=True,
        )


class KafkaContainer(TestedContainer):
    def __init__(self, host_log_folder) -> None:
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
                "KAFKA_CLUSTER_ID": "r4zt_wrqTRuT7W2NJsB_GA",
                "KAFKA_ADVERTISED_LISTENERS": "PLAINTEXT://kafka:9092",
                "KAFKA_INTER_BROKER_LISTENER_NAME": "PLAINTEXT",
                "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT",
                "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
                "KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS": "0",
            },
            allow_old_container=True,
            healthcheck={
                "test": ["CMD-SHELL", "/opt/kafka/bin/kafka-topics.sh --bootstrap-server 127.0.0.1:9092 --list",],
                "start_period": 1 * 1_000_000_000,
                "interval": 1 * 1_000_000_000,
                "timeout": 1 * 1_000_000_000,
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
            f"/opt/kafka/bin/kafka-console-consumer.sh {kafka_options} --max-messages 1 --group testgroup1 --from-beginning",
        ]

        for command in commands:
            exit_code, output = self.execute_command(test=command, interval=1 * 1_000_000_000, retries=30)
            if exit_code != 0:
                logger.stdout(f"Command {command} failed for {self._container.name}: {output}")
                self.healthy = False
                return


class CassandraContainer(TestedContainer):
    def __init__(self, host_log_folder) -> None:
        super().__init__(
            image_name="cassandra:latest",
            name="cassandra_db",
            host_log_folder=host_log_folder,
            allow_old_container=True,
        )


class RabbitMqContainer(TestedContainer):
    def __init__(self, host_log_folder) -> None:
        super().__init__(
            image_name="rabbitmq:3-management-alpine",
            name="rabbitmq",
            host_log_folder=host_log_folder,
            allow_old_container=True,
            ports={"5672": ("127.0.0.1", 5672)},
        )


class MySqlContainer(SqlDbTestedContainer):
    def __init__(self, host_log_folder) -> None:
        super().__init__(
            image_name="mariadb:latest",
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
            healthcheck={"test": ["CMD-SHELL", "healthcheck.sh --connect --innodb_initialized"], "retries": 60},
            dd_integration_service="mysql",
            db_user="mysqldb",
            db_password="mysqldb",
            db_host="mysqldb",
            db_instance="mysql_dbname",
        )


class SqlServerContainer(SqlDbTestedContainer):
    def __init__(self, host_log_folder) -> None:
        self.data_mssql = f"./{host_log_folder}/data-mssql"
        healthcheck = {}
        if not platform.processor().startswith("arm"):
            # [!NOTE] sqlcmd tool is not available inside the ARM64 version of SQL Edge containers.
            # see https://hub.docker.com/_/microsoft-azure-sql-edge
            # XXX: Using 127.0.0.1 here instead of localhost to avoid using IPv6 in some systems.
            healthcheck = {
                "test": '/opt/mssql-tools/bin/sqlcmd -S 127.0.0.1 -U sa -P "yourStrong(!)Password" -Q "SELECT 1" -b -o /dev/null',
                "retries": 20,
            }

        super().__init__(
            image_name="mcr.microsoft.com/azure-sql-edge:latest",
            name="mssql",
            environment={"ACCEPT_EULA": "1", "MSSQL_SA_PASSWORD": "yourStrong(!)Password"},
            allow_old_container=True,
            host_log_folder=host_log_folder,
            ports={"1433/tcp": ("127.0.0.1", 1433)},
            #  volumes={self.data_mssql: {"bind": "/var/opt/mssql/data", "mode": "rw"}},
            healthcheck=healthcheck,
            dd_integration_service="mssql",
            db_user="SA",
            db_password="yourStrong(!)Password",
            db_host="mssql",
            db_instance="master",
        )


class OpenTelemetryCollectorContainer(TestedContainer):
    def __init__(self, host_log_folder) -> None:
        image = os.environ.get("SYSTEM_TESTS_OTEL_COLLECTOR_IMAGE", "otel/opentelemetry-collector-contrib:latest")
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
            volumes={self._otel_config_host_path: {"bind": "/etc/otelcol-config.yml", "mode": "ro",}},
            host_log_folder=host_log_folder,
            ports={"13133/tcp": ("0.0.0.0", 13133)},
        )

    # Override wait_for_health because we cannot do docker exec for container opentelemetry-collector-contrib
    def wait_for_health(self) -> bool:
        time.sleep(20)  # It takes long for otel collector to start

        for i in range(61):
            try:
                r = requests.get(f"http://{self._otel_host}:{self._otel_port}", timeout=1)
                logger.debug(f"Healthcheck #{i} on {self._otel_host}:{self._otel_port}: {r}")
                if r.status_code == 200:
                    return True
            except Exception as e:
                logger.debug(f"Healthcheck #{i} on {self._otel_host}:{self._otel_port}: {e}")
            time.sleep(1)

        logger.stdout(f"{self._otel_host}:{self._otel_port} never answered to healthcheck request")
        return False

    def start(self) -> Container:
        # _otel_config_host_path is mounted in the container, and depending on umask,
        # it might have no read permissions for other users, which is required within
        # the container. So set them here.
        prev_mode = os.stat(self._otel_config_host_path).st_mode
        new_mode = prev_mode | stat.S_IROTH
        if prev_mode != new_mode:
            os.chmod(self._otel_config_host_path, new_mode)
        return super().start()


class APMTestAgentContainer(TestedContainer):
    def __init__(self, host_log_folder) -> None:
        super().__init__(
            image_name="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:latest",
            name="ddapm-test-agent",
            host_log_folder=host_log_folder,
            environment={"SNAPSHOT_CI": "0",},
            ports={"8126": ("127.0.0.1", 8126)},
            allow_old_container=True,
        )


class MountInjectionVolume(TestedContainer):
    def __init__(self, host_log_folder, name) -> None:
        super().__init__(
            image_name=None,
            name=name,
            host_log_folder=host_log_folder,
            command="/bin/true",
            volumes={_VOLUME_INJECTOR_NAME: {"bind": "/datadog-init", "mode": "rw"},},
        )

    def _lib_init_image(self, lib_init_image):
        self.image = ImageInfo(lib_init_image)
        if "dd-lib-js-init" in lib_init_image:
            self.kwargs["volumes"] = {
                _VOLUME_INJECTOR_NAME: {"bind": "/operator-build", "mode": "rw"},
            }
        if "dd-lib-dotnet-init" in lib_init_image:
            self.kwargs["volumes"] = {
                _VOLUME_INJECTOR_NAME: {"bind": "/datadog-init/monitoring-home", "mode": "rw"},
            }

    def remove(self):
        super().remove()
        _get_client().api.remove_volume(_VOLUME_INJECTOR_NAME)


class WeblogInjectionInitContainer(TestedContainer):
    def __init__(self, host_log_folder) -> None:

        super().__init__(
            image_name="docker.io/library/weblog-injection:latest",
            name="weblog-injection-init",
            host_log_folder=host_log_folder,
            ports={"18080": ("127.0.0.1", 8080)},
            allow_old_container=True,
            volumes={_VOLUME_INJECTOR_NAME: {"bind": "/datadog-lib", "mode": "rw"},},
        )

    def set_environment_for_library(self, library):
        lib_inject_props = {}
        for lang_env_vars in K8sWeblog.manual_injection_props["js" if library.library == "nodejs" else library.library]:
            lib_inject_props[lang_env_vars["name"]] = lang_env_vars["value"]
        lib_inject_props["DD_AGENT_HOST"] = "ddapm-test-agent"
        lib_inject_props["DD_TRACE_DEBUG"] = "true"
        self.environment = lib_inject_props
