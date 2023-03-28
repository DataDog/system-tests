# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import logging
import os
import re
import sys


class bcolors:
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    OKGREEN = "\033[92m"
    RED = "\033[91m"

    ENDC = "\033[0m"

    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def get_log_formatter():
    return logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%H:%M:%S")


def update_environ_with_local_env():

    # dynamically load .env file in environ if exists, it allow users to keep their conf via env vars
    try:
        with open(".env", "r", encoding="utf-8") as f:
            logger.debug("Found a .env file")
            for line in f:
                line = line.strip(" \t\n")
                line = re.sub(r"(.*)#.$", r"\1", line)
                line = re.sub(r"^(export +)(.*)$", r"\2", line)
                if "=" in line:
                    items = line.split("=")
                    logger.debug(f"adding {items[0]} in environ")
                    os.environ[items[0]] = items[1]

    except FileNotFoundError:
        pass


def get_logger(name="tests", use_stdout=False):
    result = logging.getLogger(name)

    if use_stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.setFormatter(get_log_formatter())
        result.addHandler(stdout_handler)

    result.setLevel(logging.DEBUG)

    return result


def o(message):
    return f"{bcolors.OKGREEN}{message}{bcolors.ENDC}"


def w(message):
    return f"{bcolors.YELLOW}{message}{bcolors.ENDC}"


def m(message):
    return f"{bcolors.BLUE}{message}{bcolors.ENDC}"


def e(message):
    return f"{bcolors.RED}{message}{bcolors.ENDC}"


logger = get_logger()
