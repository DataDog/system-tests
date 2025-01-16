import builtins
import os
import re

_not_secrets = {
    "AWS_VAULT_KEYCHAIN_NAME",  # Name of macOS keychain to use => it's a name, not a key
    "ONBOARDING_AWS_INFRA_KEY_PATH",  # TODO : what is the content of this value ?
}

_name_filter = re.compile(r"key|token|secret", re.IGNORECASE)


def _get_secrets(mode):
    secrets: list = [
        value for name, value in os.environ.items() if name not in _not_secrets and _name_filter.search(name)
    ]
    redacted = "<redacted>"

    if "b" in mode:
        secrets = [bytearray(secret, "utf-8") for secret in secrets]
        redacted = b"<redacted>"

    return secrets, redacted


def _instrument_write_methods(f):
    secrets, redacted = _get_secrets(f.mode)
    original_write = f.write

    def write(data):
        for secret in secrets:
            data = data.replace(secret, redacted)

        original_write(data)

    f.write = write


def _instrumented_open(file, mode="r", *args, **kwargs):  # noqa: ANN002
    f = _original_open(file, mode, *args, **kwargs)

    if "w" in mode or "a" in mode:
        _instrument_write_methods(f)

    return f


_original_open = builtins.open
builtins.open = _instrumented_open
