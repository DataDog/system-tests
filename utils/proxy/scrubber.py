import builtins
import os


def _get_secrets(mode):
    # if any name is added here, add it also in tests/test_the_test/test_scrubber.py
    envvars = [
        "DD_API_KEY",
        "DD_API_KEY_2",
        "DD_API_KEY_3",
        "DD_APP_KEY",
        "DD_APP_KEY_2",
        "DD_APP_KEY_3",
        "DD_APPLICATION_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        # set by CI runner
        "SYSTEM_TESTS_AWS_ACCESS_KEY_ID",
        "SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY",
    ]

    secrets: list = [os.environ[name] for name in envvars if os.environ.get(name)]
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
