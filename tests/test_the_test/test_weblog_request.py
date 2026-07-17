import http.server
import socket
import struct
import threading

from utils import scenarios
from utils._weblog import _Weblog


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port: int = s.getsockname()[1]
    s.close()
    return port


def _weblog_on(port: int) -> _Weblog:
    weblog = _Weblog()
    weblog.domain = "127.0.0.1"
    weblog.port = port
    return weblog


@scenarios.test_the_test
def test_connection_refused_is_reported() -> None:
    """Connection refused surfaces the error on response.error, not a silent status_code=None."""
    port = _free_port()  # bound then released -> connection is deterministically refused
    response = _weblog_on(port).get("/")

    assert response.status_code is None
    assert response.error is not None
    assert "127.0.0.1" in response.error
    assert response.error in repr(response)


@scenarios.test_the_test
def test_connection_reset_is_reported() -> None:
    """Connection reset also surfaces the error rather than a silent None."""
    port = _free_port()
    ready = threading.Event()

    def serve() -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(1)
        ready.set()
        conn, _ = srv.accept()
        # hard reset: close immediately with SO_LINGER(0) so the client sees a connection reset
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        conn.close()
        srv.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    assert ready.wait(5), "test server did not start"

    response = _weblog_on(port).get("/")
    thread.join(5)

    assert response.status_code is None
    assert response.error is not None


@scenarios.test_the_test
def test_successful_request_has_no_error() -> None:
    """Control: a healthy response reports status_code and no error."""
    port = _free_port()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args: object) -> None:  # silence per-request logging
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        response = _weblog_on(port).get("/")
    finally:
        srv.shutdown()
        thread.join(5)

    assert response.status_code == 200
    assert response.error is None
