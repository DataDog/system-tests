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


def _send_warmup_requests():

    if context.library in ["php", "dotnet", "cpp", "ruby", "nodejs"]:
        ok_count = 0
        for i in range(120):
            try:
                r = requests.get("http://weblog:7777", timeout=0.5)
                logger.debug(f"Warmup request #{i} result: {r}")
                if r.status_code == 200:
                    ok_count += 1
                    if ok_count == 3:
                        break
            except Exception as e:
                logger.debug(f"Warmup request #{i} result: {e}")

            time.sleep(1)

        if ok_count != 3:
            pytest.exit("App never answered to warn-up request", 1)


def _wait_for_weblog_cgroup_file():
    max_attempts = 10  # each attempt = 1 second
    attempt = 0

    while attempt < max_attempts and not os.path.exists("logs/weblog.cgroup"):
        time.sleep(1)
        attempt += 1

    if attempt == max_attempts:
        pytest.exit("Failed to access cgroup file from weblog container", 1)


def _wait_for_app_readiness():
    logger.debug("Wait for app readiness")

    t_start = time.time()
    if not interfaces.library.ready.wait(40):
        pytest.exit("Library not ready", 1)
    logger.debug(f"Library ready after {(time.time() - t_start):2f}s")

    if not interfaces.agent.ready.wait(40):
        pytest.exit("Datadog agent not ready", 1)
    logger.debug(f"Agent ready after {(time.time() - t_start):2f}s")

    _wait_for_weblog_cgroup_file()

    return


def default_warmup():
    """Check that the agent has instrumented the app"""

    _send_warmup_requests()
    _wait_for_app_readiness()

    logger.debug("Instrumentation enabled ok")
