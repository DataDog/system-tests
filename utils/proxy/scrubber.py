import builtins
import io
import os
from pathlib import Path
import re

_not_secrets = {
    "AWS_VAULT_KEYCHAIN_NAME",  # Name of macOS keychain to use => it's a name, not a key
    "ONBOARDING_AWS_INFRA_KEY_PATH",  # TODO : what is the content of this value ?
}

_name_filter = re.compile(r"key|token|secret|pass|docker_login", re.IGNORECASE)


def _get_secrets() -> set[str]:
    secrets: list = [
        value.strip()
        for name, value in os.environ.items()
        if len(value.strip()) > 6 and name not in _not_secrets and _name_filter.search(name)
    ]
    return set(secrets)


def _instrument_write_methods_str(f, secrets: set[str]) -> None:
    original_write = f.write

    def write(data):
        for secret in secrets:
            data = data.replace(secret, "<redacted>")

        original_write(data)

    f.write = write


def _instrument_write_methods_bytes(f, secrets: set[str]) -> None:
    original_write = f.write

    def write(data):
        if hasattr(data, "replace"):
            for secret in secrets:
                data = data.replace(secret.encode(), b"<redacted>")

        original_write(data)

    f.write = write


def _instrumented_open(file, mode="r", *args, **kwargs):  # noqa: ANN002
    f = _original_open(file, mode, *args, **kwargs)

    # get list of secrets at each call, because environ may be updated
    secrets = _get_secrets()

    if ("w" in mode or "a" in mode) and len(secrets) > 0:
        if "b" in mode:
            _instrument_write_methods_bytes(f, secrets)
        else:
            _instrument_write_methods_str(f, secrets)

    return f


def _instrumented_path_open(self, mode="r", *args, **kwargs):  # noqa: ANN002
    f = _original_pathlib_open(self, mode, *args, **kwargs)

    # get list of secrets at each call, because environ may be updated
    secrets = _get_secrets()

    if ("w" in mode or "a" in mode) and len(secrets) > 0:
        if "b" in mode:
            _instrument_write_methods_bytes(f, secrets)
        else:
            _instrument_write_methods_str(f, secrets)

    return f


def _instrumented_file_io(file, mode="r", *args, **kwargs):  # noqa: ANN002
    f = _original_file_io(file, mode, *args, **kwargs)

    # get list of secrets at each call, because environ may be updated
    secrets = _get_secrets()

    if ("w" in mode or "a" in mode) and len(secrets) > 0:
        _instrument_write_methods_bytes(f, secrets)

    return f


_original_open = builtins.open
builtins.open = _instrumented_open  # type: ignore[attr-defined]

_original_pathlib_open = Path.open
Path.open = _instrumented_path_open  # type: ignore[assignment]

_original_file_io = io.FileIO
io.FileIO = _instrumented_file_io  # type: ignore[misc, assignment]
