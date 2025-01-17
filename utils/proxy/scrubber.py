import builtins
import os
import re

_not_secrets = {
    "AWS_VAULT_KEYCHAIN_NAME",  # Name of macOS keychain to use => it's a name, not a key
    "ONBOARDING_AWS_INFRA_KEY_PATH",  # TODO : what is the content of this value ?
}

_name_filter = re.compile(r"key|token|secret|pass|docker_login", re.IGNORECASE)


def _get_secrets_str() -> tuple[list[str], str]:
    secrets: list = [
        value for name, value in os.environ.items() if name not in _not_secrets and _name_filter.search(name)
    ]
    redacted = "<redacted>"
    return secrets, redacted


def _get_secrets_bytes() -> tuple[list[bytes], bytes]:
    secrets: list = [
        value.encode() for name, value in os.environ.items() if name not in _not_secrets and _name_filter.search(name)
    ]
    redacted = b"<redacted>"

    return secrets, redacted


def _instrument_write_methods_str(f) -> None:
    # get list of secrets at each call, because environ may be updated
    original_write = f.write
    secrets, redacted = _get_secrets_str()
    secret_regex = re.compile("|".join(re.escape(s) for s in secrets))

    def write(data):
        data = re.sub(secret_regex, redacted, data)
        original_write(data)

    f.write = write


def _instrument_write_methods_bytes(f) -> None:
    original_write = f.write
    secrets, redacted = _get_secrets_bytes()
    secret_regex = re.compile(b"|".join(re.escape(s) for s in secrets))

    def write(data):
        data = re.sub(secret_regex, redacted, data)
        original_write(data)

    f.write = write


def _instrumented_open(file, mode="r", *args, **kwargs):  # noqa: ANN002
    f = _original_open(file, mode, *args, **kwargs)

    if "w" in mode or "a" in mode:
        if "b" in mode:
            _instrument_write_methods_bytes(f)
        else:
            _instrument_write_methods_str(f)

    return f


_original_open = builtins.open
builtins.open = _instrumented_open
