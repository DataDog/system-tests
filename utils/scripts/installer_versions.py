import os
from pathlib import Path


AUTO_INJECT_LOCK = Path(__file__).resolve().parents[2] / "auto_inject.lock"


def set_injector_version_from_lock() -> None:
    """Pin the injector when testing a custom library package."""
    if os.getenv("DD_INSTALLER_LIBRARY_VERSION") and not os.getenv("DD_INSTALLER_INJECTOR_VERSION"):
        os.environ["DD_INSTALLER_INJECTOR_VERSION"] = AUTO_INJECT_LOCK.read_text(encoding="utf-8").strip()
