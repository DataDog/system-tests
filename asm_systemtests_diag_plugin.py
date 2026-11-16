"""Mount passive proxy diagnostics and retain their tmpfs output before teardown."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_configure() -> None:
    # Wait until pytest has initialized the system-tests context.
    from utils._context.containers import ProxyContainer  # noqa: PLC0415
    from utils._context.containers import TestedContainer  # noqa: PLC0415

    wrapper_path = os.environ.get("ASM_PROXY_WRAPPER_HOST_PATH", "./asm_proxy_diagnostics.py")
    original_configure = ProxyContainer.configure
    original_remove = TestedContainer.remove
    original_stop = TestedContainer.stop

    def configured_proxy(self: ProxyContainer, *, host_log_folder: str, replay: bool) -> None:
        original_configure(self, host_log_folder=host_log_folder, replay=replay)
        if replay:
            return
        self.volumes[wrapper_path] = {"bind": "/diagnostics/asm_proxy_diagnostics.py", "mode": "ro"}
        self.command = "python /diagnostics/asm_proxy_diagnostics.py"
        if os.environ.get("ASM_PROXY_SIGNAL_STACKS") == "1":
            self.environment["ASM_PROXY_SIGNAL_STACKS"] = "1"
        else:
            self.environment.pop("ASM_PROXY_SIGNAL_STACKS", None)
        # The sibling sampler reads this proxy process's /proc/<pid>/syscall.
        self.cap_add = list(self.cap_add or [])
        if "SYS_PTRACE" not in self.cap_add:
            self.cap_add.append("SYS_PTRACE")

    def save_diagnostics(self: TestedContainer) -> None:
        if self.name != "proxy" or self._container is None or getattr(self, "_asm_diagnostics_copied", False):
            return
        destination = Path(self.log_folder_path) / "asm-proxy-diagnostics.tar"
        try:
            # Docker get_archive does not include tmpfs contents; tar inside the live container.
            result = self._container.exec_run(["tar", "-C", "/dev/shm", "-cf", "-", "asm-proxy-diagnostics"])  # noqa: S108 - Read the diagnostic tmpfs.
            if result.exit_code != 0:
                raise RuntimeError(result.output.decode(errors="replace"))  # noqa: TRY301 - Report extraction failures locally.
            destination.write_bytes(result.output)
            self._asm_diagnostics_copied = True
        except Exception as error:
            destination.with_suffix(".error.txt").write_text(repr(error))

    def remove_with_diagnostics(self: TestedContainer) -> None:
        save_diagnostics(self)
        original_remove(self)

    def stop_with_diagnostics(self: TestedContainer, *, timeout: int | None = None) -> None:
        save_diagnostics(self)
        original_stop(self, timeout=timeout)

    ProxyContainer.configure = configured_proxy
    TestedContainer.remove = remove_with_diagnostics
    TestedContainer.stop = stop_with_diagnostics
