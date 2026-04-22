# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import time
from typing import Any, cast

from utils._logger import logger

DEFAULT_CONDITION_TIMEOUT = 40.0

_CONDITIONS: list["Condition"] = []


@dataclass(frozen=True)
class Condition:
    """One thing we are waiting for after setup."""

    wait: Callable[[float], bool]
    description: str
    timeout: float = DEFAULT_CONDITION_TIMEOUT


def add(condition: Condition) -> None:
    """Register a condition for the current pytest process."""

    _CONDITIONS.append(condition)


def clear() -> None:
    """Clear registered conditions for internal tests and explicit resets."""

    _CONDITIONS.clear()


def iter_conditions() -> Iterator[Condition]:
    return iter(_CONDITIONS)


def run(*, deadline: float) -> list[Condition]:
    failed_conditions: list[Condition] = []

    for condition in _CONDITIONS:
        timeout = min(condition.timeout, max(0.0, deadline - time.time()))
        logger.info(f"Waiting for condition '{condition.description}' for up to {timeout:.1f}s")

        if condition.wait(timeout):
            logger.info(f"Condition '{condition.description}' succeeded")
        else:
            logger.warning(f"Condition '{condition.description}' did not succeed")
            failed_conditions.append(condition)

    return failed_conditions


def make_tracer_watermark(
    *,
    weblog: object,
    interfaces: object,
    endpoint: str = "/",
    timeout: float = DEFAULT_CONDITION_TIMEOUT,
) -> Condition:
    """Wait until the tracer has flushed a trace for a post-setup request.

    The watermark request is sent after setup requests are done. Once a trace
    containing that request's rid is visible on the library interface, the
    tracer has flushed at least one post-setup request to the agent proxy.
    """

    def wait_for_watermark(effective_timeout: float) -> bool:
        weblog_client = cast("Any", weblog)
        interfaces_module = cast("Any", interfaces)

        request = weblog_client.get(endpoint)

        def request_has_trace() -> bool:
            return any(True for _ in interfaces_module.library.get_spans(request=request))

        # Always check once. The timeout only controls whether we wait for new
        # captured data after the first observation failed.
        if request_has_trace():
            return True

        if effective_timeout > 0:
            interfaces_module.library.wait_for(lambda _data: request_has_trace(), effective_timeout)

        return request_has_trace()

    return Condition(
        wait=wait_for_watermark,
        description=f"tracer watermark trace for {endpoint}",
        timeout=timeout,
    )
