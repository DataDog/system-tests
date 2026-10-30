"""Run the mocked backend in its own process, e.g. in a container:

    python -m utils.mocked_backend --port 4900 --log-folder logs/interfaces/mocked_backend

It serves until it receives SIGTERM (sent by `docker stop`) or SIGINT.
"""

import argparse
import logging
from pathlib import Path
import signal
import sys
import threading
from types import FrameType

from ._backend import MockedBackendServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m utils.mocked_backend", description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=4900, help="port to listen on, 0 picks a free one (default: 4900)")
    parser.add_argument("--log-folder", help="folder where each received request is recorded (default: not recorded)")
    parser.add_argument(
        "--tls-hostname",
        action="append",
        help="serve HTTPS, with a certificate generated for this hostname, can be repeated (default: HTTP)",
    )
    parser.add_argument(
        "--internal-mocked-responses-file",
        help="JSON list of MockedBackendResponse applied for the whole session (default: none)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s", stream=sys.stdout)

    if args.log_folder:
        Path(args.log_folder).mkdir(parents=True, exist_ok=True)

    stopped = threading.Event()

    def stop(_signum: int, _frame: FrameType | None) -> None:
        stopped.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    server = MockedBackendServer(
        args.log_folder,
        port=args.port,
        tls_hostnames=args.tls_hostname,
        internal_mocked_responses_file=args.internal_mocked_responses_file,
    )
    # read by whoever started the process when the port is picked by the OS
    print(f"Mocked backend listening on port {server.port}", flush=True)  # noqa: T201
    try:
        stopped.wait()
    finally:
        server.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
