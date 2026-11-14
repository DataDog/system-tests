"""Persists the flows seen by the proxy, without blocking its event loop.

mitmproxy runs every hook on a single event loop, and sends the response to the client only once the response
hook returns. When that hook wrote the flow file synchronously, a slow disk stalled the whole proxy: during a
~14s I/O stall on a CI runner no flow was served, the PHP sidecar's trace submission timed out, and the trace
was dropped (APPSEC-71652).

This module does not depend on mitmproxy, so it can be tested from the runner.
"""

from concurrent.futures import Future, ThreadPoolExecutor
import json
import os
from typing import Any

from ._deserializer import deserialize, Interface
from .utils import logger


class ObjectDumpEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:  # noqa: ANN401
        if isinstance(o, bytes):
            return str(o)
        return json.JSONEncoder.default(self, o)


def persist_flow(
    data: dict[str, Any],
    interface: Interface,
    request_content: bytes | None,
    response_content: bytes | None,
    export_content_files_to: str,
    *,
    response_killed: bool,
) -> None:
    """Deserialize the request and response content into data, and write it to data["log_filename"]"""

    deserialize(
        data,
        key="request",
        content=request_content,
        interface=interface,
        export_content_files_to=export_content_files_to,
    )

    if response_killed:
        data["response"] = None
    else:
        deserialize(
            data,
            key="response",
            content=response_content,
            interface=interface,
            export_content_files_to=export_content_files_to,
        )

    with open(data["log_filename"], "w", encoding="utf-8", opener=lambda path, flags: os.open(path, flags, 0o777)) as f:
        json.dump(data, f, indent=2, cls=ObjectDumpEncoder)


class FlowWriter:
    """Runs persist_flow on a background thread.

    A single worker keeps the files written in the order their numbers were assigned.
    """

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="proxy-writer")

    def submit(
        self,
        flow_id: str,
        data: dict[str, Any],
        interface: Interface,
        request_content: bytes | None,
        response_content: bytes | None,
        export_content_files_to: str,
        *,
        response_killed: bool,
    ) -> Future[None]:
        """Queue the flow and return immediately. data must not be modified by the caller afterwards"""
        return self._executor.submit(
            self._persist_flow,
            flow_id,
            data,
            interface,
            request_content,
            response_content,
            export_content_files_to,
            response_killed=response_killed,
        )

    def close(self) -> None:
        """Wait for all queued flows to be written"""
        self._executor.shutdown(wait=True)

    @staticmethod
    def _persist_flow(
        flow_id: str,
        data: dict[str, Any],
        interface: Interface,
        request_content: bytes | None,
        response_content: bytes | None,
        export_content_files_to: str,
        *,
        response_killed: bool,
    ) -> None:
        # the executor would silently keep the exception in a future nobody reads: log it instead
        try:
            persist_flow(
                data,
                interface,
                request_content,
                response_content,
                export_content_files_to,
                response_killed=response_killed,
            )
        except Exception:
            logger.exception(f"Flow {flow_id}: failed to save {data.get('log_filename')}")
