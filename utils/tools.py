# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import logging
import sys
import traceback


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


def get_logger(name="tests", use_dedicated_file=False, use_stdout=False):
    result = logging.getLogger(name)

    if use_stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.setFormatter(get_log_formatter())
        result.addHandler(stdout_handler)

    if use_dedicated_file:
        file_handler = logging.FileHandler(f"logs/{name}.log")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(get_log_formatter())
        result.addHandler(file_handler)

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


def get_exception_traceback(exception):

    for line in traceback.format_exception(type(Exception), exception, exception.__traceback__):
        for subline in line.split("\n"):
            yield subline.replace('File "/app/', 'File "')


logger = get_logger()
