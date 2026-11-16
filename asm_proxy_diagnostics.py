"""Run the unchanged system-tests proxy with passive stall diagnostics.

Replace only its container command with ``python /diagnostics/asm_proxy_diagnostics.py``.
Mount this file separately; all proxy source, traffic and responses remain unchanged.
ASM_PROXY_DIAG_DIR defaults to /dev/shm/asm-proxy-diagnostics so diagnostic writes
do not share the interface log bind mount. Copy that directory before teardown.
"""

from __future__ import annotations

import asyncio
import builtins
from contextlib import suppress
import faulthandler
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Self
from urllib.parse import urlsplit


sys.path.insert(0, str(Path.cwd()))

# Keep diagnostic writes off the bind mount being investigated.
diagnostic_dir = Path(os.environ.get("ASM_PROXY_DIAG_DIR", "/dev/shm/asm-proxy-diagnostics"))  # noqa: S108
diagnostic_dir.mkdir(parents=True, exist_ok=True)
diagnostic_fd = os.open(str(diagnostic_dir / "timings.jsonl"), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
# The descriptor must stay open until faulthandler is cancelled in finally.
stack_file = builtins.open(diagnostic_dir / "stacks.log", "w", buffering=1)  # noqa: SIM115
SLOW_OPERATION_NS = 10_000_000
LOOP_LAG_THRESHOLD_NS = 50_000_000
HEARTBEAT_RECORD_INTERVAL_NS = 1_000_000_000

signal_stacks = os.environ.get("ASM_PROXY_SIGNAL_STACKS") == "1"
if signal_stacks:
    faulthandler.enable(file=stack_file, all_threads=True)
    faulthandler.dump_traceback_later(2, repeat=True, file=stack_file)


def record(event: str, **values: object) -> None:
    item = {
        "event": event,
        "wall_ns": time.time_ns(),
        "monotonic_ns": time.monotonic_ns(),
        "pid": os.getpid(),
        "thread_id": threading.get_native_id(),
        **values,
    }
    with suppress(OSError):
        os.write(diagnostic_fd, (json.dumps(item, separators=(",", ":")) + "\n").encode())


record("diagnostics_started", output=str(diagnostic_dir), signal_stacks=signal_stacks)

# This independently scheduled process samples the target process and its cgroup.
# It writes to tmpfs, so a blocked interface bind write does not block sampling.
sampler_source = r"""
import json, os, pathlib, sys, time
from typing import Optional
target = int(sys.argv[1]); destination = pathlib.Path(sys.argv[2])
fd = os.open(str(destination / 'resources.jsonl'), os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o644)
proc = pathlib.Path('/proc') / str(target)
def read(path: pathlib.Path | str) -> Optional[str]:
    try: return pathlib.Path(path).read_text()
    except (OSError, UnicodeDecodeError): return None
while proc.exists():
    cgroup = read(proc/'cgroup')
    cgroot = pathlib.Path('/sys/fs/cgroup')
    # A private cgroup namespace usually mounts this process's own cgroup at root.
    row = {'wall_ns':time.time_ns(),'monotonic_ns':time.monotonic_ns(),'target_pid':target,
           'stat':read(proc/'stat'),'status':read(proc/'status'),'io':read(proc/'io'),
           'wchan':read(proc/'wchan'),'syscall':read(proc/'syscall'),'cgroup':cgroup,
           'cpu_stat':read(cgroot/'cpu.stat'),'cpu_pressure':read(cgroot/'cpu.pressure'),
           'memory_current':read(cgroot/'memory.current'),'memory_events':read(cgroot/'memory.events'),
           'io_pressure':read(cgroot/'io.pressure'),'system_pressure_cpu':read('/proc/pressure/cpu'),
           'system_pressure_io':read('/proc/pressure/io')}
    try: os.write(fd,(json.dumps(row,separators=(',',':'))+'\n').encode())
    except OSError: pass
    time.sleep(0.25)
"""
sampler = subprocess.Popen(
    [sys.executable, "-c", sampler_source, str(os.getpid()), str(diagnostic_dir)],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)


original_emit = logging.StreamHandler.emit


def timed_emit(handler: logging.StreamHandler[Any], entry: logging.LogRecord) -> None:
    started = time.monotonic_ns()
    saving = "Saving as " in entry.getMessage()
    if saving:
        record("capture_log_enter")
    try:
        return original_emit(handler, entry)
    finally:
        elapsed = time.monotonic_ns() - started
        if saving:
            record("capture_log_exit", duration_ns=elapsed)
        if elapsed >= SLOW_OPERATION_NS:
            record(
                "slow_log_emit",
                duration_ns=elapsed,
                logger=entry.name,
                stream_name=str(getattr(handler.stream, "name", "unknown")),
            )


logging.StreamHandler.emit = timed_emit
original_open = builtins.open


class TimedInterfaceFile:
    # The proxy wraps open() without narrowing its file-object contract.
    def __init__(self, wrapped: Any, path: str) -> None:  # noqa: ANN401
        self.wrapped = wrapped
        self.path = path
        self.opened_at = time.monotonic_ns()
        self.bytes_written = 0
        self.write_ns = 0

    def __getattr__(self, key: str) -> Any:  # noqa: ANN401 - Delegate the wrapped file attribute contract.
        return getattr(self.wrapped, key)

    def __enter__(self) -> Self:
        self.wrapped.__enter__()
        return self

    def __exit__(self, *args: object) -> bool | None:
        started = time.monotonic_ns()
        record("interface_file_close_begin", path=self.path)
        try:
            return self.wrapped.__exit__(*args)
        finally:
            record(
                "interface_file_closed",
                path=self.path,
                close_ns=time.monotonic_ns() - started,
                total_ns=time.monotonic_ns() - self.opened_at,
                write_ns=self.write_ns,
                characters_written=self.bytes_written,
            )

    def write(self, data: str) -> int:
        started = time.monotonic_ns()
        try:
            return self.wrapped.write(data)
        finally:
            elapsed = time.monotonic_ns() - started
            self.write_ns += elapsed
            self.bytes_written += len(data)
            if elapsed >= SLOW_OPERATION_NS:
                record("slow_interface_write", path=self.path, duration_ns=elapsed, characters=len(data))


def timed_open(file: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401 - Preserve builtins.open arguments.
    path = str(file)
    mode = args[0] if args else kwargs.get("mode", "r")
    relevant = "/interfaces/" in path and path.endswith(".json") and any(flag in mode for flag in "wax+")
    if not relevant:
        return original_open(file, *args, **kwargs)
    started = time.monotonic_ns()
    record("interface_file_open_begin", path=path)
    wrapped = original_open(file, *args, **kwargs)
    record("interface_file_opened", path=path, duration_ns=time.monotonic_ns() - started)
    return TimedInterfaceFile(wrapped, path)


builtins.open = timed_open
original_new_loop = asyncio.new_event_loop


async def event_loop_heartbeat() -> None:
    last = time.monotonic_ns()
    last_recorded = last
    while True:
        await asyncio.sleep(0.1)
        current = time.monotonic_ns()
        lag = current - last - 100_000_000
        if lag >= LOOP_LAG_THRESHOLD_NS or current - last_recorded >= HEARTBEAT_RECORD_INTERVAL_NS:
            record("event_loop_heartbeat", lag_ns=lag)
            last_recorded = current
        last = current


def diagnosed_new_loop() -> asyncio.AbstractEventLoop:
    loop = original_new_loop()
    loop.create_task(event_loop_heartbeat())
    return loop


asyncio.new_event_loop = diagnosed_new_loop

try:
    from proxy import core

    # These temporary diagnostics intentionally wrap the proxy's private addon hooks.
    original_request = core._RequestLogger.request  # noqa: SLF001
    original_response = core._RequestLogger.response  # noqa: SLF001
    original_error = getattr(core._RequestLogger, "error", None)  # noqa: SLF001

    def request_metadata(flow: Any) -> dict[str, object]:  # noqa: ANN401 - Match mitmproxy hook objects.
        # Keep only protocol envelope identifiers; never record bodies, headers or queries.
        result: dict[str, object] = {"flow_id": flow.id, "path": urlsplit(flow.request.path).path}
        if result["path"] == "/telemetry/proxy/api/v2/apmtelemetry":
            try:
                envelope = json.loads(flow.request.content)
            except (ValueError, TypeError):
                result["envelope_valid"] = False
            else:
                if isinstance(envelope, dict):
                    for key in ("seq_id", "request_type", "runtime_id"):
                        value = envelope.get(key)
                        if isinstance(value, (str, int)):
                            result[key] = value
        return result

    def diagnosed_request(self: Any, flow: Any) -> Any:  # noqa: ANN401 - Preserve the original addon callback.
        record("request_received", **request_metadata(flow))
        return original_request(self, flow)

    def diagnosed_error(self: Any, flow: Any) -> Any:  # noqa: ANN401 - Preserve the original addon callback.
        message = str(getattr(flow.error, "msg", "")).lower()
        category = next(
            (word for word in ("timeout", "disconnect", "killed", "tls", "connect", "protocol") if word in message),
            "other",
        )
        record("request_error", error_category=category, **request_metadata(flow))
        if original_error is not None:
            return original_error(self, flow)
        return None

    def diagnosed_response(self: Any, flow: Any) -> Any:  # noqa: ANN401 - Preserve the original addon callback.
        started = time.monotonic_ns()
        record("response_handler_enter", response_status=flow.response.status_code, **request_metadata(flow))
        try:
            return original_response(self, flow)
        finally:
            record("response_handler_exit", duration_ns=time.monotonic_ns() - started, **request_metadata(flow))

    core._RequestLogger.request = diagnosed_request  # noqa: SLF001
    core._RequestLogger.response = diagnosed_response  # noqa: SLF001
    core._RequestLogger.error = diagnosed_error  # noqa: SLF001
    record("proxy_starting")
    core.start_proxy()
finally:
    record("proxy_exiting")
    if signal_stacks:
        faulthandler.cancel_dump_traceback_later()
    sampler.terminate()
    try:
        sampler.wait(timeout=2)
    except subprocess.TimeoutExpired:
        sampler.kill()
    stack_file.close()
    os.close(diagnostic_fd)
