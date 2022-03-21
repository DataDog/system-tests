# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
A warmup is a function that will be executed before test session. It's stored in context
"""
import os

import requests
import time
import pytest

from utils import context, interfaces
from utils.tools import logger


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
                r = requests.get(self.url, timeout=0.5)
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

    while attempt < max_attempts and not os.path.exists("logs/weblog.cgroup"):
        time.sleep(1)
        attempt += 1

    if attempt == max_attempts:
        pytest.exit("Failed to access cgroup file from weblog container", 1)

    return True


def _wait_for_app_readiness():
    logger.debug("Wait for app readiness")

    if not interfaces.library.ready.wait(40):
        pytest.exit("Library not ready", 1)
    logger.debug(f"Library ready")

    if not interfaces.agent.ready.wait(40):
        pytest.exit("Datadog agent not ready", 1)
    logger.debug(f"Agent ready")

    _wait_for_weblog_cgroup_file()

    return


def add_default_warmups():

    # need help from Colin: which port with UDS ?
    context.add_warmup(_HealthCheck("http://agent:8126/info", 60, start_period=15))
    context.add_warmup(_HealthCheck("http://library_proxy:8126/info", 60))
    context.add_warmup(_HealthCheck("http://weblog:7777", 120))
    context.add_warmup(_wait_for_app_readiness)
