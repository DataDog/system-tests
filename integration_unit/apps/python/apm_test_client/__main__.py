import logging
import os

from .server import serve


logging.basicConfig(level=logging.DEBUG)
serve(port=os.getenv("APM_TEST_CLIENT_SERVER_PORT") or "50051")
