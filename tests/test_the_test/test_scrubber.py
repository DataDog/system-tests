import os
from pathlib import Path
import subprocess
import sys
import textwrap

from utils import pytest
from utils import scenarios
from utils.proxy.scrubber import SecretInEnvironmentError, check_no_secret_in_env, get_secret_env_names


FILENAME = "tests/test_the_test/test_scrubber.py"

secret_names = {
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

not_secret_names = {
    "AWS_VAULT_KEYCHAIN_NAME": "a_keychain_name",  # explicitly excluded name
    "ONBOARDING_AWS_INFRA_KEY_PATH": "/path/to/key.pem",  # explicitly excluded name
    "ONBOARDING_AWS_INFRA_KEYPAIR_NAME": "a_keypair_name",  # explicitly excluded name
    "SOME_PASSWORD": "datadog",  # explicitly excluded value
    "SHORT_TOKEN": "  123456  ",  # too short once stripped
    "DD_SITE": "datad0g.com",  # name does not match
}


@scenarios.test_the_test
def test_secrets_are_detected():
    assert get_secret_env_names(secret_names | not_secret_names) == sorted(secret_names)


@scenarios.test_the_test
def test_name_filter_is_case_insensitive():
    assert get_secret_env_names({"my_api_key": "a_long_value", "Docker_Login": "a_long_value"}) == [
        "Docker_Login",
        "my_api_key",
    ]


@scenarios.test_the_test
def test_no_secret_does_not_raise():
    check_no_secret_in_env(not_secret_names)


@scenarios.test_the_test
def test_error_names_variables_but_never_values():
    with pytest.raises(SecretInEnvironmentError) as exc_info:
        check_no_secret_in_env(secret_names | not_secret_names)

    message = str(exc_info.value)
    assert exc_info.value.names == sorted(secret_names)
    for name in secret_names:
        assert name in message
    for value in (secret_names | not_secret_names).values():
        assert value not in message


def _env_without_secrets() -> dict[str, str]:
    return {name: value for name, value in os.environ.items() if name not in get_secret_env_names()}


@scenarios.test_the_test
def test_runner_fails_fast():
    cmd = ["./run.sh", "MOCK_THE_TEST", FILENAME]
    result = subprocess.run(cmd, env=_env_without_secrets() | secret_names, text=True, capture_output=True, check=False)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "look like secrets" in output, output
    for name in secret_names:
        assert name in output
    for secret in secret_names.values():
        assert secret not in output, f"{secret} found in run.sh output"

    # nothing ran, so nothing could leak in the logs
    for path in Path("logs_mock_the_test").rglob("*"):
        if path.is_file():
            data = path.read_text(encoding="utf-8", errors="replace")
            for secret in secret_names.values():
                assert secret not in data, f"{secret} found in {path}"


@scenarios.test_the_test
def test_proxy_write_scrubber(tmp_path: Path):
    """The proxy still redacts env secrets from what it writes. Run in a subprocess: it patches builtins"""

    script = textwrap.dedent(
        """
        import io, json, sys
        from pathlib import Path
        from utils.proxy.scrubber import install_write_scrubber

        install_write_scrubber()

        folder = Path(sys.argv[1])
        secret = "datad0g_secret"
        content = f"/var/log/{secret} {secret}_preload_hook"

        with open(folder / "str.txt", "w") as f:
            f.write(content)
            f.writelines([content, content])
        with open(folder / "json.json", "w") as f:
            json.dump({"str": secret, "int": 123456789}, f)
        with open(folder / "bytes.bin", "wb") as f:
            assert f.write(content.encode()) == len(content)
        with Path(folder / "pathlib.txt").open("w") as f:
            f.write(content)
        with io.FileIO(folder / "fileio.bin", "w") as f:
            f.write(content.encode())
        """
    )

    env = _env_without_secrets() | {"PYTHONPATH": ".", "A_SECRET": "datad0g_secret", "INT_KEY": "123456789"}
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=env, check=True)

    files = list(tmp_path.iterdir())
    assert len(files) == 5
    for file in files:
        data = file.read_text(encoding="utf-8")
        assert "datad0g_secret" not in data, file
        assert "123456789" not in data, file

    # binary writes keep the size
    assert len((tmp_path / "bytes.bin").read_bytes()) == len("/var/log/datad0g_secret datad0g_secret_preload_hook")
    assert "--redacted--" in (tmp_path / "str.txt").read_text(encoding="utf-8")
