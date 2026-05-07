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


def _telemetry_emitter_key(data: dict) -> tuple[str, str]:
    """Return the (runtime_id, user_agent) identity of a telemetry record.

    Two separate axes can produce independent telemetry streams:
    - runtime_id: weblogs with multiple worker processes (gunicorn, OpenLiberty)
      each have their own runtime_id and flush independently.
    - user_agent: some tracers run two concurrent telemetry emitters under the
      same runtime_id — one from the tracer itself (no User-Agent or a tracer
      UA) and one from libdatadog (UA "telemetry/…"). Each emitter has its own
      flush schedule, so we must wait for each one separately.
    """
    content = data["request"]["content"]
    runtime_id = content.get("runtime_id", "") if isinstance(content, dict) else ""
    headers = {h[0].lower(): h[1] for h in (data["request"].get("headers") or [])}
    ua = headers.get("user-agent", "")
    return (runtime_id, ua)


def _wait_for_telemetry_flush(
    interfaces_module: object, watermark_log: str, effective_timeout: float, start: float
) -> None:
    """After the watermark trace is visible, wait until every (runtime_id, user_agent)
    pair that was sending telemetry before the watermark has sent at least one
    telemetry message after the watermark.

    This ensures that any metrics accumulated during setup (e.g. IAST
    executed.sink) are present in the interface before the test asserts on them.
    """
    ifaces = cast("Any", interfaces_module)

    pairs_before: set[tuple[str, str]] = set()
    for data in ifaces.library.get_telemetry_data(flatten_message_batches=False):
        if data["log_filename"] < watermark_log:
            pairs_before.add(_telemetry_emitter_key(data))

    if not pairs_before:
        return

    def pairs_after_watermark() -> set[tuple[str, str]]:
        result: set[tuple[str, str]] = set()
        for data in ifaces.library.get_telemetry_data(flatten_message_batches=False):
            if data["log_filename"] > watermark_log:
                result.add(_telemetry_emitter_key(data))
        return result

    def all_pairs_flushed(_data: object) -> bool:
        return pairs_before <= pairs_after_watermark()

    remaining = max(0.0, effective_timeout - (time.time() - start))
    if remaining > 0 and not all_pairs_flushed(None):
        ifaces.library.wait_for(all_pairs_flushed, remaining)


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

        start = time.time()
        request = weblog_client.get(endpoint)

        def request_has_trace() -> bool:
            return any(True for _ in interfaces_module.library.get_spans(request=request))

        if not request_has_trace() and effective_timeout > 0:
            interfaces_module.library.wait_for(lambda _data: request_has_trace(), effective_timeout)

        if not request_has_trace():
            return False

        # Find the log_filename of the record that contains the watermark span.
        # log_filename is zero-padded (e.g. "…/00011__v0.4_traces.json"), so
        # lexicographic order == arrival order.
        watermark_log = next(
            (data["log_filename"] for data, _trace, _span in interfaces_module.library.get_spans(request=request)),
            None,
        )

        if watermark_log is not None:
            _wait_for_telemetry_flush(interfaces_module, watermark_log, effective_timeout, start)

        return True

    return Condition(
        wait=wait_for_watermark,
        description=f"tracer watermark trace for {endpoint}",
        timeout=timeout,
    )
