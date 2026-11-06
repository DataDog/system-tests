"""Standalone helpers: this package must not import the rest of utils (see .importlinter), so it can
run in its own container.
"""

import logging

CONTROL_URL_PREFIX = "/system-tests"
"""Prefix of every endpoint used to control the mocked backend, rather than mimicking the real one"""

HOST_DOCKER_INTERNAL = "host.docker.internal"

# Domain of the mocked backend, also the DD_SITE of its senders: the intake hostnames derived from it are its network
# aliases. The reserved .invalid domain fails closed if a request is sent anywhere else
MOCKED_BACKEND_DOMAIN = "mocked-backend.invalid"

# child of the system-tests "tests" logger: in the test process, records still reach its handlers
logger = logging.getLogger("tests.mocked_backend")
