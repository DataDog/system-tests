import os
from pathlib import Path
import subprocess
import sys
import textwrap

from utils import pytest
from utils import scenarios, logger
from utils.proxy.scrubber import (
    SecretInEnvironmentError,
    check_no_secret_in_env,
    get_runner_secret_policy,
    get_secret_env_names,
    is_ci,
)


FILENAME = "tests/test_the_test/test_scrubber.py"
CI_NAMES = ("CI", "GITHUB_ACTIONS", "GITLAB_CI")

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


# --- secret detection ---


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


# --- strict mode vs excluded runs ---


@scenarios.test_the_test
@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({}, False),
        ({"CI": "true"}, True),  # GitHub Actions and GitLab CI
        ({"CI": "false"}, False),
        ({"GITHUB_ACTIONS": "true"}, True),
        ({"GITLAB_CI": "true"}, True),
    ],
)
def test_is_ci(environ: dict[str, str], *, expected: bool):
    assert is_ci(environ) is expected


@scenarios.test_the_test
def test_runner_secret_policy():
    ci = {"CI": "true"}

    assert get_runner_secret_policy(needs_secrets_on_runner=False, generate_cassettes=False, environ=ci) is None
    assert get_runner_secret_policy(needs_secrets_on_runner=True, generate_cassettes=False, environ=ci) is not None
    assert get_runner_secret_policy(needs_secrets_on_runner=False, generate_cassettes=True, environ=ci) is not None
    assert get_runner_secret_policy(needs_secrets_on_runner=False, generate_cassettes=False, environ={}) is not None


@scenarios.test_the_test
def test_scenarios_needing_secrets_on_runner():
    # SSI scenarios provision VMs or K8s clusters from the runner
    assert scenarios.simple_installer_auto_injection.needs_secrets_on_runner
    assert scenarios.k8s_lib_injection.needs_secrets_on_runner
    assert scenarios.k8s_injector_dev_single_service.needs_secrets_on_runner

    # everything else runs in strict mode in CI
    assert not scenarios.docker_ssi.needs_secrets_on_runner
    assert not scenarios.default.needs_secrets_on_runner
    assert not scenarios.parametric.needs_secrets_on_runner
    assert not scenarios.mock_the_test.needs_secrets_on_runner


def _clean_env(*, ci: bool) -> dict[str, str]:
    """Current env, without secrets, with or without CI"""
    hidden = set(get_secret_env_names()) | set(CI_NAMES)
    result = {name: value for name, value in os.environ.items() if name not in hidden}
    if ci:
        result["CI"] = "true"
    return result


def _run_mock_the_test(env: dict[str, str], *extra_args: str) -> subprocess.CompletedProcess:
    cmd = ["./run.sh", "MOCK_THE_TEST", FILENAME, *extra_args]
    return subprocess.run(cmd, env=env, text=True, capture_output=True, check=False)


def _assert_no_secret_in_logs() -> int:
    """Return how many redactions were found"""
    redacted_count = 0
    for path in Path("logs_mock_the_test").rglob("*"):
        if path.is_file():
            data = path.read_text(encoding="utf-8", errors="replace")
            redacted_count += data.count("--redacted--")
            for secret in secret_names.values():
                assert secret not in data, f"{secret} found in {path}"
    return redacted_count


@scenarios.test_the_test
def test_strict_mode_fails_fast_in_ci():
    result = _run_mock_the_test(_clean_env(ci=True) | secret_names)

    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "look like secrets" in output, output
    for name in secret_names:
        assert name in output
    for secret in secret_names.values():
        assert secret not in output, f"{secret} found in run.sh output"

    _assert_no_secret_in_logs()


@scenarios.test_the_test
def test_local_run_redacts_secrets():
    result = _run_mock_the_test(_clean_env(ci=False) | secret_names)

    assert "look like secrets" not in result.stdout + result.stderr
    assert _assert_no_secret_in_logs() != 0, "No secrets were redacted"


@scenarios.test_the_test
def test_cassette_recording_redacts_secrets_in_ci():
    result = _run_mock_the_test(_clean_env(ci=True) | secret_names, "--generate-cassettes")

    assert "look like secrets" not in result.stdout + result.stderr
    assert _assert_no_secret_in_logs() != 0, "No secrets were redacted"


@scenarios.mock_the_test
def test_leaks():
    logger.info(os.environ)
    print(os.environ)  # noqa: T201


# --- write-time redaction ---


@scenarios.test_the_test
def test_write_scrubber(tmp_path: Path):
    """Run in a subprocess: install_write_scrubber patches builtins"""

    script = textwrap.dedent(
        """
        import io, json, os, sys
        from pathlib import Path
        from utils.proxy import scrubber

        calls = 0
        original_get_secret_env_names = scrubber.get_secret_env_names

        def counting_get_secret_env_names(*args, **kwargs):
            global calls
            calls += 1
            return original_get_secret_env_names(*args, **kwargs)

        scrubber.get_secret_env_names = counting_get_secret_env_names
        scrubber.install_write_scrubber()
        scrubber.install_write_scrubber()  # idempotent

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
        for i in range(100):
            with open(folder / f"many_{i}.txt", "w") as f:
                f.write(content)

        # the secret list is computed once, at install: a secret added later is not known
        os.environ["LATE_SECRET"] = "late_secret_value"
        with open(folder / "late.txt", "w") as f:
            f.write("late_secret_value")

        assert calls == 1, f"secret list computed {calls} times"
        """
    )

    env = _clean_env(ci=False) | {"PYTHONPATH": ".", "A_SECRET": "datad0g_secret", "INT_KEY": "123456789"}
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=env, check=True)

    for file in tmp_path.iterdir():
        if file.name == "late.txt":
            continue
        data = file.read_text(encoding="utf-8")
        assert "datad0g_secret" not in data, file
        assert "123456789" not in data, file

    assert (tmp_path / "late.txt").read_text(encoding="utf-8") == "late_secret_value"

    # binary writes keep the size
    assert len((tmp_path / "bytes.bin").read_bytes()) == len("/var/log/datad0g_secret datad0g_secret_preload_hook")
    assert "--redacted--" in (tmp_path / "str.txt").read_text(encoding="utf-8")


@scenarios.test_the_test
def test_write_scrubber_without_secret_is_a_noop():
    script = textwrap.dedent(
        """
        import builtins
        from utils.proxy.scrubber import install_write_scrubber

        original_open = builtins.open
        install_write_scrubber()
        assert builtins.open is original_open
        """
    )

    subprocess.run([sys.executable, "-c", script], env=_clean_env(ci=False) | {"PYTHONPATH": "."}, check=True)
