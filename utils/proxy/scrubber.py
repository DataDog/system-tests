"""Detection of secrets in the environment.

The test runner must never hold a secret: `check_no_secret_in_env` is called at startup and fails fast,
naming the offending variables (never their values).

The proxy is different: it sits between the agent and the real Datadog backend in some scenarios, so real API
keys flow through it (in request headers), and it receives DD_API_KEY/DD_APP_KEY in its environment. For this
reason it still redacts those values from everything it writes, see `install_write_scrubber`.

Those modules are shared by the runner and the proxy container (that only mounts utils/proxy), so they must
only depend on the standard library.
"""

import builtins
import io
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_not_secret_names = {
    "AWS_VAULT_KEYCHAIN_NAME",  # Name of macOS keychain to use => it's a name, not a key
    "ONBOARDING_AWS_INFRA_KEY_PATH",  # key pair local path
    "ONBOARDING_AWS_INFRA_KEYPAIR_NAME",  # key pair name
}

_not_secret_values = {"datadog"}
""" Values present in env var, but that are not secret """

_name_filter = re.compile(r"key|token|secret|pass|docker_login", re.IGNORECASE)

_MINIMUM_SECRET_LENGTH = 6  # below this size, we don't consider it a secret


def _is_secret(name: str, value: str) -> bool:
    stripped_value = value.strip()
    return (
        len(stripped_value) > _MINIMUM_SECRET_LENGTH
        and name not in _not_secret_names
        and stripped_value not in _not_secret_values
        and _name_filter.search(name) is not None
    )


def get_secret_env_names(environ: Mapping[str, str] | None = None) -> list[str]:
    """Names of the env vars that look like secrets"""
    environ = os.environ if environ is None else environ
    return sorted(name for name, value in environ.items() if _is_secret(name, value))


class SecretInEnvironmentError(Exception):
    def __init__(self, names: list[str]):
        self.names = names
        super().__init__(
            "The following environment variables look like secrets and must not be present in the test runner "
            f"environment: {', '.join(names)}. Unset them before running system-tests. "
            f"(A variable is considered as a secret if its name matches /{_name_filter.pattern}/i and its "
            f"value is longer than {_MINIMUM_SECRET_LENGTH} characters, see utils/proxy/scrubber.py)"
        )


def check_no_secret_in_env(environ: Mapping[str, str] | None = None) -> None:
    """Raise SecretInEnvironmentError if any env var looks like a secret. Only names are reported, never values"""
    names = get_secret_env_names(environ)
    if names:
        raise SecretInEnvironmentError(names)


# --- write-time scrubbing, only used by the proxy ---


def _get_secrets() -> set[str]:
    return {os.environ[name].strip() for name in get_secret_env_names()}


def _instrument_write_methods_str(f: Any, secrets: set[str]) -> None:  # noqa: ANN401
    original_write = f.write

    def write(data: str):
        for secret in secrets:
            data = data.replace(secret, "--redacted--")

        return original_write(data)

    f.write = write


def _instrument_write_methods_bytes(f: Any, secrets: set[str]) -> None:  # noqa: ANN401
    original_write = f.write

    def write(data: bytes):
        if hasattr(data, "replace"):
            for secret in secrets:
                encoded_secret = secret.encode()
                data = data.replace(encoded_secret, b"*" * len(encoded_secret))

        return original_write(data)

    f.write = write


def install_write_scrubber() -> None:
    """Redact secrets found in the environment from any file written with open, Path.open or io.FileIO.

    The secret list is computed once: the proxy's environment does not change after startup.
    """
    secrets = _get_secrets()
    if not secrets:
        return

    original_open = builtins.open
    original_pathlib_open = Path.open
    original_file_io = io.FileIO

    def instrument(f: Any, mode: str) -> None:  # noqa: ANN401
        if "w" in mode or "a" in mode:
            if "b" in mode:
                _instrument_write_methods_bytes(f, secrets)
            else:
                _instrument_write_methods_str(f, secrets)

    def instrumented_open(file: Any, mode: str = "r", *args, **kwargs):  # noqa: ANN002, ANN003, ANN401
        f = original_open(file, mode, *args, **kwargs)
        instrument(f, mode)
        return f

    def instrumented_path_open(self: Path, mode: str = "r", *args, **kwargs):  # noqa: ANN002, ANN003
        f = original_pathlib_open(self, mode, *args, **kwargs)
        instrument(f, mode)
        return f

    def instrumented_file_io(file: str, mode: str = "r", *args, **kwargs):  # noqa: ANN002, ANN003
        f = original_file_io(file, mode, *args, **kwargs)
        instrument(f, mode + "b")  # FileIO is always binary
        return f

    builtins.open = instrumented_open  # type: ignore[assignment]
    Path.open = instrumented_path_open  # type: ignore[assignment]
    io.FileIO = instrumented_file_io  # type: ignore[misc, assignment]
