from contextlib import suppress
from pathlib import Path
import shlex
import time
import uuid

from paramiko.client import SSHClient
from paramiko.sftp_client import SFTPClient

from utils import scenarios, context, features, irrelevant, bug, logger
from utils.onboarding.injection_log_parser import command_injection_skipped


_LOG_STABILITY_TIMEOUT_SECONDS = 10.0
_LOG_STABILITY_POLL_SECONDS = 0.1
_LOG_STABLE_OBSERVATIONS = 5


def _get_remote_file_size(sftp: SFTPClient, remote_path: str) -> int:
    size = sftp.stat(remote_path).st_size
    if size is None:
        raise RuntimeError(f"Could not determine the size of remote log file [{remote_path}]")
    return size


def _copy_remote_file(ssh_client: SSHClient, source_path: str, destination_path: str) -> None:
    copy_command = f"cp -- {shlex.quote(source_path)} {shlex.quote(destination_path)}"
    _, stdout, stderr = ssh_client.exec_command(copy_command)
    error_output = stderr.read().decode("utf-8", errors="replace")
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        raise RuntimeError(
            f"Could not create stable snapshot [{destination_path}] from [{source_path}]: {error_output}"
        )


def _wait_for_stable_remote_log(
    ssh_client: SSHClient,
    sftp: SFTPClient,
    remote_log_path: str,
    snapshot_path: str,
) -> None:
    deadline = time.monotonic() + _LOG_STABILITY_TIMEOUT_SECONDS
    previous_size = -1
    stable_observations = 0

    while time.monotonic() < deadline:
        try:
            current_size = _get_remote_file_size(sftp, remote_log_path)
        except OSError:
            time.sleep(_LOG_STABILITY_POLL_SECONDS)
            continue

        if current_size > 0 and current_size == previous_size:
            stable_observations += 1
        else:
            previous_size = current_size
            stable_observations = 1

        if stable_observations >= _LOG_STABLE_OBSERVATIONS:
            _copy_remote_file(ssh_client, remote_log_path, snapshot_path)
            snapshot_size = _get_remote_file_size(sftp, snapshot_path)
            source_size = _get_remote_file_size(sftp, remote_log_path)

            if snapshot_size == source_size == current_size:
                time.sleep(_LOG_STABILITY_POLL_SECONDS)
                if _get_remote_file_size(sftp, remote_log_path) == source_size:
                    return

            previous_size = -1
            stable_observations = 0

        time.sleep(_LOG_STABILITY_POLL_SECONDS)

    raise TimeoutError(f"Remote log file did not become stable: [{remote_log_path}]")


def _download_stable_remote_log(ssh_client: SSHClient, remote_log_path: str, local_log_path: Path) -> None:
    snapshot_path = f"{remote_log_path}.snapshot"
    sftp = ssh_client.open_sftp()
    try:
        with suppress(OSError):
            sftp.remove(snapshot_path)

        _wait_for_stable_remote_log(ssh_client, sftp, remote_log_path, snapshot_path)
        sftp.get(snapshot_path, str(local_log_path))
    finally:
        with suppress(OSError):
            sftp.remove(snapshot_path)
        sftp.close()


class _AutoInjectWorkloadSelectionBaseTest:
    """Base class to test workload selection policies on auto instrumentation."""

    def _execute_remote_command(self, ssh_client: SSHClient, command: str) -> str:
        """Execute remote command and get remote log file from the vm. You can use this method using env variables or using injection config file"""

        unique_log_name = f"host_injection_{uuid.uuid4()}.log"
        remote_log_path = f"/var/log/datadog_weblog/{unique_log_name}"

        command_with_config = (
            "DD_APM_INSTRUMENTATION_DEBUG=TRUE "
            f"DD_APM_INSTRUMENTATION_OUTPUT_PATHS={shlex.quote(remote_log_path)} {command}"
        )
        logger.info(f"Executing command: [{command_with_config}] associated with log file: [{unique_log_name}]")
        local_log_path = Path(context.scenario.host_log_folder) / unique_log_name

        _, stdout, stderr = ssh_client.exec_command(command_with_config)
        logger.info("Command output:")
        logger.info(stdout.readlines())
        logger.info("Command err output:")
        logger.info(stderr.readlines())
        exit_status = stdout.channel.recv_exit_status()
        logger.info(f"Command exit status: [{exit_status}]")

        _download_stable_remote_log(ssh_client, remote_log_path, local_log_path)

        return str(local_log_path)


@features.host_block_list
@scenarios.installer_auto_injection
@irrelevant(condition=context.weblog_variant == "test-app-dotnet-iis")
class TestAutoInjectWorkloadSelectionInstallManualHost(_AutoInjectWorkloadSelectionBaseTest):
    """Test that auto instrumentation respects workload selection policies (excluded specific commands and args)."""

    # Commands with args excluded by workload selection policy per language (should not be instrumented)
    commands_excluded_by_workload_policy = {
        "java": ["java -version", "MY_ENV_VAR=hello java -version"],
        "dotnet": [
            "dotnet restore",
            "dotnet build -c Release",
            "dotnet publish",
            "MY_ENV_VAR=hello dotnet build -c Release",
        ],
    }

    # Commands with args included by workload selection policy per language (should be instrumented)
    commands_not_excluded_by_workload_policy = {
        "java": [
            "java -jar myjar.jar",
            "sudo -E java -jar myjar.jar",
            "version=-version java -jar myjar.jar",
            "java -Dversion=-version -jar myapp.jar",
        ],
        "dotnet": [
            "dotnet run -- -p build",
            "dotnet build.dll -- -p build",
            "sudo -E dotnet run myapp.dll -- -p build",
            "MY_ENV_VAR=build dotnet myapp.dll",
        ],
    }

    no_language_found_commands = [
        "touch myfile.txt",
        "hello=hola cat myfile.txt",
        "ls -la",
        "mkdir newdir",
    ]

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_no_language_found_commands(self) -> None:
        """Check that commands with no language found are skipped from auto injection."""
        virtual_machine = context.virtual_machine
        logger.info(f"[{virtual_machine.get_ip()}] Executing commands with no language found")
        ssh_client = virtual_machine.get_ssh_connection()
        for command in self.no_language_found_commands:
            local_log_file = self._execute_remote_command(ssh_client, command)
            assert command_injection_skipped(command, local_log_file), (
                f"The command '{command}' was allowed by auto injection but should have been denied"
            )

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_commands_denied_by_workload_selection(self) -> None:
        """Check that commands are skipped from auto injection based on workload selection policies."""
        virtual_machine = context.virtual_machine
        logger.info(f"[{virtual_machine.get_ip()}] Executing commands that are denied by workload selection policies")
        language = context.library.name
        if language not in self.commands_excluded_by_workload_policy:
            return
        ssh_client = virtual_machine.get_ssh_connection()
        for command in self.commands_excluded_by_workload_policy[language]:
            local_log_file = self._execute_remote_command(ssh_client, command)
            assert command_injection_skipped(command, local_log_file), (
                f"The command '{command}' was allowed by auto injection but should have been denied"
            )

    @bug(
        context.virtual_machine.os_distro == "rpm" and context.weblog_variant == "test-app-dotnet",
        reason="APMSP-4036",
    )
    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_commands_allowed_by_workload_selection(self) -> None:
        """Check that commands are allowed to be instrumented based on workload selection policies."""
        virtual_machine = context.virtual_machine
        logger.info(f"[{virtual_machine.get_ip()}] Executing commands that are allowed by workload selection policies")
        language = context.library.name
        if language not in self.commands_not_excluded_by_workload_policy:
            return
        ssh_client = virtual_machine.get_ssh_connection()
        for command in self.commands_not_excluded_by_workload_policy[language]:
            local_log_file = self._execute_remote_command(ssh_client, command)
            assert command_injection_skipped(command, local_log_file) is False, (
                f"The command '{command}' was denied by auto injection but should have been allowed"
            )
