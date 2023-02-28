# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import os
import json
import time
import pytest
import requests

from utils._context.containers import TestedContainer
from utils._context.library_version import LibraryVersion, Version
from utils.tools import logger


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

        try:
            with open(f"logs/.{image_name}.env", encoding="ascii") as f:
                for line in f:
                    if line.strip():
                        key, value = line.split("=", 1)
                        self.env[key] = value.strip()
        except FileNotFoundError:
            pass


class _Context:  # pylint: disable=too-many-instance-attributes
    def __init__(self):

        self.proxy_state = None
        self.dd_site = os.environ.get("DD_SITE")

        self.agent_image = ImageInfo("agent")
        self.weblog_image = ImageInfo("weblog")

        self.appsec_rules_file = self.weblog_image.env.get("DD_APPSEC_RULES", None)
        self.uds_socket = self.weblog_image.env.get("DD_APM_RECEIVER_SOCKET", None)

        self.library = LibraryVersion(
            self.weblog_image.env.get("SYSTEM_TESTS_LIBRARY", None),
            self.weblog_image.env.get("SYSTEM_TESTS_LIBRARY_VERSION", None),
        )
        self.weblog_variant = self.weblog_image.env.get("SYSTEM_TESTS_WEBLOG_VARIANT", None)

        if self.library == "php":
            self.php_appsec = Version(self.weblog_image.env.get("SYSTEM_TESTS_PHP_APPSEC_VERSION"), "php_appsec")
        else:
            self.php_appsec = None

        libddwaf_version = self.weblog_image.env.get("SYSTEM_TESTS_LIBDDWAF_VERSION", None)

        if not libddwaf_version:
            self.libddwaf_version = None
        else:
            self.libddwaf_version = Version(libddwaf_version, "libddwaf")

        appsec_rules_version = self.weblog_image.env.get("SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION", "0.0.0")
        self.appsec_rules_version = Version(appsec_rules_version, "appsec_rules")

        agent_version = self.agent_image.env.get("SYSTEM_TESTS_AGENT_VERSION")

        if not agent_version:
            self.agent_version = None
        else:
            self.agent_version = Version(agent_version, "agent")

        self.weblog_env = self._init_weblog_env()

        self.scenario = os.environ.get("SYSTEMTESTS_SCENARIO", "DEFAULT")
        self._init_scenario()

        self.agent_container = TestedContainer(
            image_name="system_tests/agent",
            name="agent",
            environment={
                "DD_API_KEY": os.environ.get("DD_API_KEY", "please-set-DD_API_KEY"),
                "DD_ENV": "system-tests",
                "DD_HOSTNAME": "test",
                "DD_SITE": os.environ.get("DD_SITE", "datad0g.com"),
                "DD_APM_RECEIVER_PORT": "8126",
                "DD_DOGSTATSD_PORT": "8125",  # TODO : move this in agent build ?
            },
        )

        self.weblog_container = TestedContainer(
            image_name="system_tests/weblog",
            name="weblog",
            environment=self.weblog_env,
            volumes={f"./{self.host_log_folder}/docker/weblog/logs/": {"bind": "/var/log/system-tests", "mode": "rw"},},
            # ddprof's perf event open is blocked by default by docker's seccomp profile
            # This is worse than the line above though prevents mmap bugs locally
            security_opt=["seccomp=unconfined"],
        )

        self.cassandra_db = TestedContainer(
            image_name="cassandra:latest", name="cassandra_db", allow_old_container=True
        )

        self.mongo_db = TestedContainer(image_name="mongo:latest", name="mongodb", allow_old_container=True)
        self.postgres_db = TestedContainer(
            image_name="postgres:latest",
            name="postgres",
            user="postgres",
            environment={"POSTGRES_PASSWORD": "password", "PGPORT": "5433"},
            volumes={
                "./utils/build/docker/postgres-init-db.sh": {
                    "bind": "/docker-entrypoint-initdb.d/init_db.sh",
                    "mode": "ro",
                }
            },
        )

    def _init_weblog_env(self):
        """ returns the default weblog environment """

        result = {
            "DD_AGENT_HOST": os.environ.get("DD_AGENT_HOST", "runner"),
            "DD_TRACE_AGENT_PORT": self.agent_port,
            "DD_APPSEC_ENABLED": "true",
            "DD_TELEMETRY_HEARTBEAT_INTERVAL": "2",
        }

        if self.library in ("cpp", "dotnet", "java", "python"):
            result["DD_TRACE_HEADER_TAGS"] = "user-agent:http.request.headers.user-agent"
        elif self.library in ("golang", "nodejs", "php", "ruby"):
            result["DD_TRACE_HEADER_TAGS"] = "user-agent"

        return result

    def _init_scenario(self):
        self.weblog_env["SYSTEMTESTS_SCENARIO"] = self.scenario

        if self.scenario == "SAMPLING":
            self.weblog_env["DD_TRACE_SAMPLE_RATE"] = "0.5"
        elif self.scenario == "APPSEC_MISSING_RULES":
            self.weblog_env["DD_APPSEC_RULES"] = "/donotexists"
        elif self.scenario == "APPSEC_CORRUPTED_RULES":
            self.weblog_env["DD_APPSEC_RULES"] = "/appsec_corrupted_rules.yml"
        elif self.scenario == "APPSEC_CUSTOM_RULES":
            self.weblog_env["DD_APPSEC_RULES"] = "/appsec_custom_rules.json"
        elif self.scenario == "APPSEC_BLOCKING":
            self.weblog_env["DD_APPSEC_RULES"] = "/appsec_blocking_rule.json"
        elif self.scenario == "APPSEC_RULES_MONITORING_WITH_ERRORS":
            self.weblog_env["DD_APPSEC_RULES"] = "/appsec_custom_rules_with_errors.json"
        elif self.scenario == "APPSEC_DISABLED":
            self.weblog_env["DD_APPSEC_ENABLED"] = "false"
        elif self.scenario == "APPSEC_LOW_WAF_TIMEOUT":
            self.weblog_env["DD_APPSEC_WAF_TIMEOUT"] = "1"
        elif self.scenario == "APPSEC_CUSTOM_OBFUSCATION":
            self.weblog_env["DD_APPSEC_OBFUSCATION_PARAMETER_KEY_REGEXP"] = "hide-key"
            self.weblog_env["DD_APPSEC_OBFUSCATION_PARAMETER_VALUE_REGEXP"] = ".*hide_value"
        elif self.scenario == "APPSEC_RATE_LIMITER":
            self.weblog_env["DD_APPSEC_TRACE_RATE_LIMIT"] = "1"
        elif self.scenario == "LIBRARY_CONF_CUSTOM_HEADERS_SHORT":
            self.weblog_env["DD_TRACE_HEADER_TAGS"] += ",header-tag1,header-tag2"
        elif self.scenario == "LIBRARY_CONF_CUSTOM_HEADERS_LONG":
            self.weblog_env["DD_TRACE_HEADER_TAGS"] += ",header-tag1:custom.header-tag1,header-tag2:custom.header-tag2"
        elif self.scenario == "TRACE_PROPAGATION_STYLE_W3C":
            self.weblog_env["DD_TRACE_PROPAGATION_STYLE_INJECT"] = "W3C"
            self.weblog_env["DD_TRACE_PROPAGATION_STYLE_EXTRACT"] = "W3C"
        elif self.scenario == "INTEGRATIONS":
            self.weblog_env["DD_DBM_PROPAGATION_MODE"] = "full"
        elif self.scenario == "APPSEC_WAF_TELEMETRY":
            self.weblog_env["DD_INSTRUMENTATION_TELEMETRY_ENABLED"] = "true"
        elif self.scenario == "APPSEC_IP_BLOCKING":
            self.proxy_state = '{"mock_remote_config_backend": "ASM_DATA"}'
        elif self.scenario == "APPSEC_RUNTIME_ACTIVATION":
            self.proxy_state = '{"mock_remote_config_backend": "ASM_ACTIVATE_ONLY"}'
            del self.weblog_env["DD_APPSEC_ENABLED"]
            self.weblog_env["DD_RC_TARGETS_KEY_ID"] = "TEST_KEY_ID"
            self.weblog_env["DD_RC_TARGETS_KEY"] = "1def0961206a759b09ccdf2e622be20edf6e27141070e7b164b7e16e96cf402c"
            self.weblog_env["DD_REMOTE_CONFIG_INTEGRITY_CHECK_ENABLED"] = "true"
        elif self.scenario == "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES":
            self.proxy_state = '{"mock_remote_config_backend": "ASM_FEATURES"}'
            del self.weblog_env["DD_APPSEC_ENABLED"]
            self.weblog_env["DD_REMOTE_CONFIGURATION_ENABLED"] = "true"
        elif self.scenario == "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING":
            self.proxy_state = '{"mock_remote_config_backend": "LIVE_DEBUGGING"}'
            self.weblog_env["DD_DYNAMIC_INSTRUMENTATION_ENABLED"] = "1"
            self.weblog_env["DD_DEBUGGER_ENABLED"] = "1"
            self.weblog_env["DD_REMOTE_CONFIG_ENABLED"] = "true"
            self.weblog_env["DD_INTERNAL_RCM_POLL_INTERVAL"] = "1000"
        elif self.scenario == "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD":
            self.proxy_state = '{"mock_remote_config_backend": "ASM_DD"}'
        elif self.scenario == "REMOTE_CONFIG_MOCKED_BACKEND_ASM_FEATURES_NOCACHE":
            self.proxy_state = '{"mock_remote_config_backend": "ASM_FEATURES_NO_CACHE"}'
            self.weblog_env["DD_APPSEC_ENABLED"] = "false"
            self.weblog_env["DD_REMOTE_CONFIGURATION_ENABLED"] = "true"
        elif self.scenario == "REMOTE_CONFIG_MOCKED_BACKEND_LIVE_DEBUGGING_NOCACHE":
            self.proxy_state = '{"mock_remote_config_backend": "LIVE_DEBUGGING_NO_CACHE"}'
            self.weblog_env["DD_DYNAMIC_INSTRUMENTATION_ENABLED"] = "1"
            self.weblog_env["DD_DEBUGGER_ENABLED"] = "1"
            self.weblog_env["DD_REMOTE_CONFIG_ENABLED"] = "true"
        elif self.scenario == "REMOTE_CONFIG_MOCKED_BACKEND_ASM_DD_NOCACHE":
            self.proxy_state = '{"mock_remote_config_backend": "ASM_DD_NO_CACHE"}'
        elif self.scenario == "APM_TRACING_E2E_SINGLE_SPAN":
            self.weblog_env[
                "DD_SPAN_SAMPLING_RULES"
            ] = '[{"service": "weblog", "name": "*single_span_submitted", "sample_rate": 1.0, "max_per_second": 50}]'
            self.weblog_env["DD_TRACE_SAMPLE_RATE"] = "0"

    @property
    def host_log_folder(self):
        return f"logs_{self.scenario.lower()}" if self.scenario != "DEFAULT" else "logs"

    @property
    def uds_mode(self):
        return self.uds_socket is not None

    @property
    def agent_port(self):
        return os.environ.get("DD_TRACE_AGENT_PORT", 8126)

    @property
    def tracer_sampling_rate(self):
        if "DD_TRACE_SAMPLE_RATE" not in self.weblog_env:
            return None

        return float(self.weblog_env["DD_TRACE_SAMPLE_RATE"])

    @property
    def required_containers(self):
        result = []

        if self.scenario in ("INTEGRATIONS",):
            result.append(self.mongo_db)
            result.append(self.cassandra_db)
            result.append(self.postgres_db)
        elif self.scenario in ("DEFAULT",):
            result.append(self.postgres_db)

        return result

    def execute_warmups(self):
        warmups = []

        for container in self.required_containers:
            warmups.append(container.start)

        warmups += [
            self.agent_container.start,
            _HealthCheck(f"http://agent:{self.agent_port}/info", 60, start_period=1),
            self.weblog_container.start,
            _HealthCheck("http://weblog:7777", 60),
            _wait_for_app_readiness,
        ]

        if self.scenario == "CGROUP":

            # cgroup test
            # require a dedicated warmup. Need to check the stability before
            # merging it into the default scenario

            warmups.append(_wait_for_weblog_cgroup_file)

        for warmup in warmups:
            logger.info(f"Executing warmup {warmup}")
            warmup()

    def collect_logs(self):
        try:
            self.agent_container.save_logs()
            self.weblog_container.save_logs()
        except:
            logger.exception("Fail to save logs")

    def close_targets(self):
        self.agent_container.remove()
        self.weblog_container.remove()

        for container in self.required_containers:
            container.remove()

    def serialize(self):
        result = {
            "agent": str(self.agent_version),
            "library": self.library.serialize(),
            "weblog_variant": self.weblog_variant,
            "dd_site": self.dd_site,
            "sampling_rate": self.tracer_sampling_rate,
            "libddwaf_version": str(self.libddwaf_version),
            "appsec_rules_file": self.appsec_rules_file or "*default*",
            "uds_socket": self.uds_socket,
            "scenario": self.scenario,
        }

        if self.library == "php":
            result["php_appsec"] = self.php_appsec

        return result

    def __str__(self):
        return json.dumps(self.serialize(), indent=4)


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


def _wait_for_weblog_cgroup_file():
    max_attempts = 10  # each attempt = 1 second
    attempt = 0

    while attempt < max_attempts and not os.path.exists("logs/docker/weblog/logs/weblog.cgroup"):

        logger.debug("logs/docker/weblog/logs/weblog.cgroup is missing, wait")
        time.sleep(1)
        attempt += 1

    if attempt == max_attempts:
        pytest.exit("Failed to access cgroup file from weblog container", 1)

    return True


def _wait_for_app_readiness():
    from utils import interfaces  # import here to avoid circular import

    logger.debug("Wait for app readiness")

    if not interfaces.library.ready.wait(40):
        pytest.exit("Library not ready", 1)
    logger.debug("Library ready")

    if not interfaces.agent.ready.wait(40):
        pytest.exit("Datadog agent not ready", 1)
    logger.debug("Agent ready")


context = _Context()
