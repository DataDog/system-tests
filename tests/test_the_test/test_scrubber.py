import io
import json
import os
from pathlib import Path
import subprocess
import pytest
from utils import scenarios, missing_feature, logger


FILENAME = "tests/test_the_test/test_scrubber.py"

scrubbed_names = {
    "DD_API_KEY": "secret_value_1",
    "DD_API_KEY_2": "secret_value_C",
    "DD_API_KEY_3": "secret_value_D",
    "DD_APP_KEY": "secret_value_2",
    "DD_APP_KEY_2": "secret_value_A",
    "DD_APP_KEY_3": "secret_value_B",
    "DD_APPLICATION_KEY": "secret_value_3",
    "AWS_ACCESS_KEY_ID": "secret_value_4",
    "AWS_SECRET_ACCESS_KEY": "secret_value_5",
    "AWS_SESSION_TOKEN": "secret_value_6",
    "AWS_SECURITY_TOKEN": "secret_value_7",
    "SYSTEM_TESTS_AWS_ACCESS_KEY_ID": "secret_value_8",
    "SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY": "secret_value_9",
    # Env variables loaded by SSI tests
    "DD_API_KEY_ONBOARDING": "secret_value_onboarding_1",
    "DD_APP_KEY_ONBOARDING": "secret_value_onboarding_2",
    "GITHUB_TOKEN": "secret_value_onboarding_3",
    "DOCKER_LOGIN": "secret_value_onboarding_4",
    "DOCKER_LOGIN_PASS": "secret_value_onboarding_5",
}


@scenarios.test_the_test
def test_log_scrubber():
    cmd = ["./run.sh", "MOCK_THE_TEST", FILENAME]
    subprocess.run(cmd, env=scrubbed_names | os.environ, text=True, capture_output=True, check=False)

    redacted_count = 0

    for root, _, files in os.walk("logs_mock_the_test"):
        for file in files:
            file_path = os.path.join(root, file)

            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()

            redacted_count += data.count("--redacted--")
            for secret in scrubbed_names.values():
                assert secret not in data, f"{secret} found in {file_path}"

    # extra protection to make sure we redacted all secrets
    assert redacted_count != 0, "No secrets were redacted"


@scenarios.mock_the_test
def test_leaks():
    logger.info(os.environ)
    print(os.environ)  # noqa: T201


@scenarios.test_the_test
@pytest.mark.parametrize(("write_mode", "read_mode", "file_extension"), [("w", "r", "txt"), ("wb", "rb", "bin")])
def test_file_writer_scrubber(write_mode: str, read_mode: str, file_extension: str):
    secrets = []

    for name, value in scrubbed_names.items():
        os.environ[name] = value
        secrets.append(bytearray(value, "utf-8") if write_mode == "wb" else value)

    log_file = f"{scenarios.test_the_test.host_log_folder}/leak.{file_extension}"
    with open(log_file, write_mode) as f:
        for secret in secrets:
            f.write(secret)
            f.writelines([secret, secret])

    with open(log_file, read_mode) as f:
        data = f.read()

    for secret in secrets:
        assert secret not in data


@scenarios.test_the_test
def test_jsonweird():
    secret = 123456789
    os.environ["KEY_SCRUBBED"] = f"{secret}"

    log_file = "logs_test_the_test/json_weird.json"
    with open(log_file, "w") as f:
        json.dump({"int": secret, "str": f"{secret}"}, f)

    del os.environ["KEY_SCRUBBED"]

    with open(log_file, "r") as f:
        data = f.read()

    assert f"{secret}" not in data


@scenarios.test_the_test
def test_pathlib():
    secret = 123456789
    os.environ["KEY_SCRUBBED"] = f"{secret}"

    log_file = "logs_test_the_test/pathlib.txt"
    with Path(log_file).open("w") as f:
        json.dump({"int": secret, "str": f"{secret}"}, f)
        f.writelines([f"{secret}"])

    del os.environ["KEY_SCRUBBED"]

    with open(log_file, "r") as f:
        data = f.read()

    assert f"{secret}" not in data


@scenarios.test_the_test
@missing_feature(condition=True, reason="Not supported")
def test_os_open():
    secret = 123456789
    os.environ["KEY_SCRUBBED"] = f"{secret}"

    log_file = "logs_test_the_test/os_open.txt"
    fd = os.open(log_file, os.O_WRONLY | os.O_CREAT)
    os.write(fd, f"{secret}".encode())
    os.close(fd)

    del os.environ["KEY_SCRUBBED"]

    with open(log_file, "r") as f:
        data = f.read()

    assert f"{secret}" not in data


@scenarios.test_the_test
def test_io_file():
    secret = 123456789
    os.environ["KEY_SCRUBBED"] = f"{secret}"

    log_file = "logs_test_the_test/io_fileio.txt"
    with io.FileIO(log_file, "w") as f:
        f.write(f"{secret}".encode())

    del os.environ["KEY_SCRUBBED"]

    with open(log_file, "r") as f:
        data = f.read()

    assert f"{secret}" not in data
