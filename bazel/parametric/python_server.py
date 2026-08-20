from __future__ import annotations

import importlib
import os
from pathlib import Path
import socket


def _listening_socket(port: int) -> socket.socket:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("0.0.0.0", port))  # noqa: S104 - isolated PRoot test server
    server_socket.listen(socket.SOMAXCONN)
    return server_socket


def _publish_port(server_socket: socket.socket) -> None:
    ready_file = os.environ.get("APM_TEST_CLIENT_READY_FILE")
    if not ready_file:
        return
    port = int(server_socket.getsockname()[1])
    Path(ready_file).write_text(str(port), encoding="utf-8")


def main() -> None:
    importlib.import_module("ddtrace.auto")
    uvicorn = importlib.import_module("uvicorn")
    port = int(os.environ.get("APM_TEST_CLIENT_SERVER_PORT", "80"))
    server_socket = _listening_socket(port)
    _publish_port(server_socket)
    config = uvicorn.Config(
        "apm_test_client.server:app",
        host="0.0.0.0",  # noqa: S104 - isolated PRoot test server
        port=port,
        log_level="debug",
    )
    uvicorn.Server(config).run(sockets=[server_socket])


if __name__ == "__main__":
    main()
