# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from enum import StrEnum
import logging
import os
import re
import sys
from typing import Any


class ShColors(StrEnum):
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    OKGREEN = "\033[92m"
    RED = "\033[91m"

    ENDC = "\033[0m"

    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def get_log_formatter() -> logging.Formatter:
    return logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%H:%M:%S")


def update_environ_with_local_env() -> None:
    # dynamically load .env file in environ if exists, it allow users to keep their conf via env vars
    try:
        with open(".env", encoding="utf-8") as f:
            logger.debug("Found a .env file")
            for raw_line in f:
                line = raw_line.strip(" \t\n")
                line = re.sub(r"(.*)#.$", r"\1", line)
                line = re.sub(r"^(export +)(.*)$", r"\2", line)
                if "=" in line:
                    items = line.split("=")
                    logger.debug(f"adding {items[0]} in environ")
                    os.environ[items[0]] = items[1]

    except FileNotFoundError:
        pass


DEBUG_LEVEL_STDOUT = 100


class Logger(logging.Logger):
    terminal: Any

    def stdout(self, message, *args, **kws) -> None:  # noqa: ANN002
        if self.isEnabledFor(DEBUG_LEVEL_STDOUT):
            # Yes, logger takes its '*args' as 'args'.
            self._log(DEBUG_LEVEL_STDOUT, message, args, **kws)  # pylint: disable=protected-access

            if hasattr(self, "terminal"):
                self.terminal.write_line(message)
                self.terminal.flush()
            else:
                # at this point, the logger may not yet be configured with the pytest terminal
                # so directly print in stdout
                print(message)  # noqa: T201


logging.setLoggerClass(Logger)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.addLevelName(DEBUG_LEVEL_STDOUT, "STDOUT")


def get_logger(name="tests", *, use_stdout=False) -> Logger:
    result: Logger = logging.getLogger(name)  # type: ignore[assignment]

    if use_stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.setFormatter(get_log_formatter())
        result.addHandler(stdout_handler)

    result.setLevel(logging.DEBUG)

    return result


def o(message: str) -> str:
    return f"{ShColors.OKGREEN}{message}{ShColors.ENDC}"


def w(message: str) -> str:
    return f"{ShColors.YELLOW}{message}{ShColors.ENDC}"


def m(message: str) -> str:
    return f"{ShColors.BLUE}{message}{ShColors.ENDC}"


def e(message: str) -> str:
    return f"{ShColors.RED}{message}{ShColors.ENDC}"


logger = get_logger()


def get_rid_from_request(request) -> str | None:
    if request is None:
        return None

    user_agent = next(v for k, v in request.request.headers.items() if k.lower() == "user-agent")
    return user_agent[-36:]


def get_rid_from_span(span) -> str | None:
    if not isinstance(span, dict):
        logger.error(f"Span should be an object, not {type(span)}")
        return None

    meta = span.get("meta", {})
    metrics = span.get("metrics", {})

    user_agent = None

    if span.get("type") == "rpc":
        user_agent = meta.get("grpc.metadata.user-agent")
        # java does not fill this tag; it uses the normal http tags

    if not user_agent and metrics.get("_dd.top_level") == 1.0:
        # The top level span (aka root span) is mark via the _dd.top_level tag by the tracers
        user_agent = meta.get("http.request.headers.user-agent")

    if not user_agent:  # try something for .NET
        user_agent = meta.get("http_request_headers_user-agent")

    if not user_agent:
        # cpp tracer
        user_agent = meta.get("http_user_agent")

    if not user_agent:  # last hope
        user_agent = meta.get("http.useragent")

    if not user_agent:  # last last hope (java opentelemetry autoinstrumentation)
        user_agent = meta.get("user_agent.original")

    if not user_agent:  # last last last hope (python opentelemetry autoinstrumentation)
        user_agent = meta.get("http.user_agent")

    return get_rid_from_user_agent(user_agent)


def get_rid_from_user_agent(user_agent: str) -> str | None:
    if not user_agent:
        return None

    match = re.search("rid/([A-Z]{36})", user_agent)

    if not match:
        return None

    return match.group(1)


def nested_lookup(needle: str, heystack, *, look_in_keys=False, exact_match=False) -> bool:
    """Look for needle in heystack, heystack can be a dict or an array"""

    if isinstance(heystack, str):
        return (needle == heystack) if exact_match else (needle in heystack)

    if isinstance(heystack, (list, tuple)):
        for item in heystack:
            if nested_lookup(needle, item, look_in_keys=look_in_keys, exact_match=exact_match):
                return True

        return False

    if isinstance(heystack, dict):
        for key, value in heystack.items():
            if look_in_keys and nested_lookup(needle, key, look_in_keys=look_in_keys, exact_match=exact_match):
                return True

            if nested_lookup(needle, value, look_in_keys=look_in_keys, exact_match=exact_match):
                return True

        return False

    if isinstance(heystack, (bool, float, int)) or heystack is None:
        return False

    raise TypeError(f"Can't handle type {type(heystack)}")
