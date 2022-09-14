# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import os
import json
import pytest
import requests
import time

from utils.tools import logger, get_exception_traceback
from utils._context.library_version import LibraryVersion, Version


class ImageInfo:
    """data on docker image. data comes from `docker inspect`"""

    def __init__(self, image_name):
        self.env = {}

        try:
            self._raw = json.load(open(f"logs/{image_name}_image.json"))
        except FileNotFoundError:
            return  # silently fail, needed for testing

        for var in self._raw[0]["Config"]["Env"]:
            key, value = var.split("=", 1)
            self.env[key] = value

        try:
            with open(f"logs/.{image_name}.env") as f:
                for line in f:
                    if line.strip():
                        key, value = line.split("=", 1)
                        self.env[key] = value.strip()
        except FileNotFoundError:
            pass


class _Context:
    def __init__(self):
        self.agent_image = ImageInfo("agent")
        self.weblog_image = ImageInfo("weblog")

        if "DD_APPSEC_RULES" in self.weblog_image.env:
            self.appsec_rules_file = self.weblog_image.env["DD_APPSEC_RULES"]
        else:
            self.appsec_rules_file = None

        self.dd_site = os.environ.get("DD_SITE")

        self.scenario = self.weblog_image.env.get("SYSTEMTESTS_SCENARIO", "DEFAULT")

        library = self.weblog_image.env.get("SYSTEM_TESTS_LIBRARY", None)
        version = self.weblog_image.env.get("SYSTEM_TESTS_LIBRARY_VERSION", None)
        self.library = LibraryVersion(library, version)

        self.weblog_variant = self.weblog_image.env.get("SYSTEM_TESTS_WEBLOG_VARIANT", None)

        if "DD_TRACE_SAMPLE_RATE" in self.weblog_image.env:
            sampling_rate = self.weblog_image.env["DD_TRACE_SAMPLE_RATE"]
            try:
                self.sampling_rate = float(sampling_rate)
            except:
                pytest.exit(f"DD_TRACE_SAMPLE_RATE should be a float, not {sampling_rate}")
        else:
            self.sampling_rate = None

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

    def execute_warmups(self):

        agent_port = os.environ["SYSTEM_TESTS_AGENT_DD_APM_RECEIVER_PORT"]

        warmups = [
            _HealthCheck(f"http://agent:{agent_port}/info", 60, start_period=15),
            _HealthCheck(f"http://library_proxy:{agent_port}/info", 60),
            _HealthCheck("http://weblog:7777", 120),
            _wait_for_app_readiness,
        ]

        if self.scenario == "CGROUP":
            warmups.append(_wait_for_weblog_cgroup_file)

        for warmup in warmups:
            logger.info(f"Executing warmup {warmup}")
            try:
                warmup()
            except Exception as e:
                logger.error("\n".join(get_exception_traceback(e)))
                pytest.exit(f"{warmup} failed: {e}", 1)

    def serialize(self):
        result = {
            "agent": str(self.agent_version),
            "library": self.library.serialize(),
            "weblog_variant": self.weblog_variant,
            "dd_site": self.dd_site,
            "sampling_rate": self.sampling_rate,
            "libddwaf_version": str(self.libddwaf_version),
            "appsec_rules_file": self.appsec_rules_file or "*default*",
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
                r = requests.get(self.url, timeout=3)
                logger.debug(f"Healthcheck #{i} on {self.url}: {r}")
                if r.status_code == 200:
                    return True
            except Exception as e:
                logger.debug(f"Healthcheck #{i} on {self.url}: {e}")

            time.sleep(self.interval)

        pytest.exit(f"{self.url} never answered to healthcheck request", 1)

    def __str__(self):
        return f"Healthcheck({repr(self.url)}, retries={self.retries}, interval={self.interval}, start_period={self.start_period})"


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
    logger.debug(f"Library ready")

    if not interfaces.agent.ready.wait(40):
        pytest.exit("Datadog agent not ready", 1)
    logger.debug(f"Agent ready")

    return


context = _Context()
