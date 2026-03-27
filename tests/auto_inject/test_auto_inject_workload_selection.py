import uuid
from scp import SCPClient

from utils import scenarios, context, features, irrelevant, logger
from utils.onboarding.injection_log_parser import command_injection_skipped


class _AutoInjectWorkloadSelectionBaseTest:
    """Base class to test workload selection policies on auto instrumentation."""

    def _execute_remote_command(self, ssh_client, command):
        """Execute remote command and get remote log file from the vm. You can use this method using env variables or using injection config file"""

        unique_log_name = f"host_injection_{uuid.uuid4()}.log"

        command_with_config = f"DD_APM_INSTRUMENTATION_DEBUG=TRUE DD_APM_INSTRUMENTATION_OUTPUT_PATHS=/var/log/datadog_weblog/{unique_log_name} {command}"
        logger.info(f"Executing command: [{command_with_config}] associated with log file: [{unique_log_name}]")
        log_local_path = context.scenario.host_log_folder + f"/{unique_log_name}"

        _, stdout, stderr = ssh_client.exec_command(command_with_config)
        logger.info("Command output:")
        logger.info(stdout.readlines())
        logger.info("Command err output:")
        logger.info(stderr.readlines())

        scp = SCPClient(ssh_client.get_transport())
        scp.get(remote_path=f"/var/log/datadog_weblog/{unique_log_name}", local_path=log_local_path)

        return log_local_path


@features.host_block_list
@scenarios.installer_auto_injection
@irrelevant(condition=context.weblog_variant == "test-app-dotnet-iis")
class TestAutoInjectWorkloadSelectionInstallManualHost(_AutoInjectWorkloadSelectionBaseTest):
    """Test that auto instrumentation respects workload selection policies (excluded specific commands and args)."""

    # Commands excluded by workload selection policy (should not be instrumented)
    no_language_found_commands = [
        "touch myfile.txt",
        "hello=hola cat myfile.txt",
        "ls -la",
        "mkdir newdir",
    ]

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
            "java -jar myjar.jar",
            "version=-version java -jar myjar.jar",
            "java -Dversion=-version -jar myapp.jar",
        ],
        "dotnet": [
            "dotnet run -- -p build",
            "dotnet build.dll -- -p build",
            "dotnet run myapp.dll -- -p build",
            "dotnet publish",
            "MY_ENV_VAR=build dotnet myapp.dll",
        ],
    }

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_no_language_found_commands(self):
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
    def test_commands_denied_by_workload_selection(self):
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

    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_commands_allowed_by_workload_selection(self):
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
