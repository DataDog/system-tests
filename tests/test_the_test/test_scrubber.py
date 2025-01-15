import os
import subprocess
import pytest
from utils import scenarios
from utils.tools import logger


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
    # set by CI runner
    "SYSTEM_TESTS_AWS_ACCESS_KEY_ID": "secret_value_8",
    "SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY": "secret_value_9",
}


@scenarios.test_the_test
def test_log_scrubber():
    cmd = ["./run.sh", "MOCK_THE_TEST", FILENAME]
    subprocess.run(cmd, env=scrubbed_names | os.environ, text=True, capture_output=True)

    redacted_count = 0

    for root, _, files in os.walk("logs_mock_the_test"):
        for file in files:
            file_path = os.path.join(root, file)

            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()

            redacted_count += data.count("<redacted>")
            for secret in scrubbed_names.values():
                assert secret not in data, f"{secret} found in {file_path}"

    # extra portection to make sure we redacted all secrets
    assert redacted_count == 39


@scenarios.mock_the_test
def test_leaks():
    logger.info(os.environ)
    print(os.environ)


@scenarios.test_the_test
@pytest.mark.parametrize("write_mode, read_mode, file_extension", [("w", "r", "txt"), ("wb", "rb", "bin")])
def test_file_writer_scrubber(write_mode, read_mode, file_extension):
    secrets = []

    for name, secret in scrubbed_names.items():
        os.environ[name] = secret
        secrets.append(bytearray(secret, "utf-8") if write_mode == "wb" else secret)

    log_file = f"{scenarios.test_the_test.host_log_folder}/leak.{file_extension}"
    with open(log_file, write_mode) as f:
        for secret in secrets:
            f.write(secret)
            f.writelines([secret, secret])

    with open(log_file, read_mode) as f:
        data = f.read()

    for secret in secrets:
        assert secret not in data
