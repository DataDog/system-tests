"""Opt-in Gunicorn lifecycle evidence for direct Feature Flags EVP tests."""

from datetime import UTC, datetime
import json
import os
import sys
from typing import Any


DIRECT_EVP_SHUTDOWN_MARKER_EVENT = "system_tests.ffe.shutdown.server_closed"


def worker_exit(_server: Any, _worker: Any) -> None:
    """Mark the worker closed before interpreter shutdown flushes buffered events."""
    if os.environ.get("SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED") != "true":
        return

    marker = {
        "event": DIRECT_EVP_SHUTDOWN_MARKER_EVENT,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    sys.stdout.write(json.dumps(marker, separators=(",", ":")) + "\n")
    sys.stdout.flush()
