import logging
import os

from .test_client_server import serve


__all__ = [
    "serve"
]

logging.basicConfig(level=logging.DEBUG)
serve(port=os.getenv("APM_TEST_CLIENT_SERVER_PORT") or "50051")
