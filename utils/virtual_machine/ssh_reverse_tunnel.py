"""SSH reverse tunnel: exposes a port of the test runner on a VM's loopback interface.

This lets processes running on the VM (e.g. the Datadog agent) reach a server running in the
pytest process (e.g. the mocked backend) through ``http://127.0.0.1:<remote_port>`` on the VM,
without any network rule allowing the VM to open connections to the test runner: the traffic
rides on the SSH connection the runner already opens to the VM.
"""

from __future__ import annotations

import contextlib
import select
import socket
import threading
from typing import TYPE_CHECKING

from utils._logger import logger

if TYPE_CHECKING:
    import paramiko

    from utils.virtual_machine.virtual_machines import _VirtualMachine

_BUFFER_SIZE = 32768
_KEEPALIVE_INTERVAL = 30
_MONITOR_INTERVAL = 10


class SSHReverseTunnel:
    """Forwards connections made to ``127.0.0.1:remote_port`` on the VM to ``local_host:local_port``
    on the test runner (equivalent of ``ssh -R remote_port:local_host:local_port``).
    """

    def __init__(
        self, virtual_machine: _VirtualMachine, remote_port: int, local_port: int, local_host: str = "127.0.0.1"
    ) -> None:
        self.virtual_machine = virtual_machine
        self.remote_port = remote_port
        self.local_port = local_port
        self.local_host = local_host
        self._client: paramiko.SSHClient | None = None
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._monitor: threading.Thread | None = None

    @property
    def remote_url(self) -> str:
        """URL to use on the VM to reach the forwarded local server"""
        return f"http://127.0.0.1:{self.remote_port}"

    def start(self) -> None:
        with self._lock:
            self._start()
        self._stopped.clear()
        self._monitor = threading.Thread(target=self._monitor_loop, name="ssh-reverse-tunnel-monitor", daemon=True)
        self._monitor.start()

    def _monitor_loop(self) -> None:
        while not self._stopped.wait(_MONITOR_INTERVAL):
            try:
                self.ensure_alive()
            except Exception as e:
                logger.error(f"SSH reverse tunnel to {self.virtual_machine.name}: failed to re-open it: {e}")

    def _start(self) -> None:
        client = self.virtual_machine.get_ssh_connection()
        transport = client.get_transport()
        assert transport is not None, "SSH connection has no transport"
        transport.set_keepalive(_KEEPALIVE_INTERVAL)
        try:
            transport.request_port_forward("127.0.0.1", self.remote_port, handler=self._on_channel)
        except Exception:
            client.close()
            raise
        self._client = client
        logger.info(
            f"SSH reverse tunnel opened: {self.virtual_machine.name}:127.0.0.1:{self.remote_port} -> "
            f"{self.local_host}:{self.local_port}"
        )

    def is_alive(self) -> bool:
        if self._client is None:
            return False
        transport = self._client.get_transport()
        return transport is not None and transport.is_active()

    def ensure_alive(self) -> None:
        """Re-open the tunnel if the SSH connection was dropped (e.g. network hiccup, sshd restart)"""
        with self._lock:
            if self._client is not None and self.is_alive():
                return
            logger.warning(f"SSH reverse tunnel to {self.virtual_machine.name} is down, re-opening it")
            self._close()
            self._start()

    def stop(self) -> None:
        self._stopped.set()
        if self._monitor is not None:
            self._monitor.join(timeout=_MONITOR_INTERVAL + 5)
            self._monitor = None
        with self._lock:
            self._close()

    def _close(self) -> None:
        if self._client is None:
            return
        transport = self._client.get_transport()
        if transport is not None and transport.is_active():
            with contextlib.suppress(Exception):
                transport.cancel_port_forward("127.0.0.1", self.remote_port)
        with contextlib.suppress(Exception):
            self._client.close()
        self._client = None
        logger.info(f"SSH reverse tunnel to {self.virtual_machine.name} closed")

    def _on_channel(self, channel: paramiko.Channel, _origin: tuple, _server: tuple) -> None:
        # Called from the paramiko transport thread: it must not block
        threading.Thread(target=self._pipe, args=(channel,), name="ssh-reverse-tunnel", daemon=True).start()

    def _pipe(self, channel: paramiko.Channel) -> None:
        try:
            sock = socket.create_connection((self.local_host, self.local_port), timeout=10)
        except OSError as e:
            logger.error(f"SSH reverse tunnel: can't connect to {self.local_host}:{self.local_port}: {e}")
            channel.close()
            return

        sock.settimeout(None)
        try:
            while True:
                readable, _, _ = select.select([sock, channel], [], [], 1)
                if sock in readable:
                    data = sock.recv(_BUFFER_SIZE)
                    if not data:
                        break
                    channel.sendall(data)
                if channel in readable:
                    data = channel.recv(_BUFFER_SIZE)
                    if not data:
                        break
                    sock.sendall(data)
        except OSError as e:
            logger.debug(f"SSH reverse tunnel: connection closed with error: {e}")
        finally:
            with contextlib.suppress(Exception):
                channel.close()
            with contextlib.suppress(Exception):
                sock.close()
