import uuid
from scp import SCPClient

from utils import scenarios, context, features, irrelevant
from utils.tools import logger
from utils.onboarding.injection_log_parser import command_injection_skipped
from utils.virtual_machine.utils import parametrize_virtual_machines


class _AutoInjectBlockListBaseTest:
    """Base class to test the block list on auto instrumentation"""

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
class TestAutoInjectBlockListInstallManualHost(_AutoInjectBlockListBaseTest):
    builtin_args_commands_block = {
        "java": ["java -version", "MY_ENV_VAR=hello java -version"],
        "donet": [
            "dotnet restore",
            "dotnet build -c Release",
            "sudo -E dotnet publish",
            "MY_ENV_VAR=hello dotnet build -c Release",
        ],
    }

    builtin_args_commands_injected = {
        "java": [
            "java -jar myjar.jar",
            "sudo -E java -jar myjar.jar",
            "version=-version java -jar myjar.jar",
            "java -Dversion=-version -jar myapp.jar",
        ],
        "donet": [
            "dotnet run -- -p build",
            "dotnet build.dll -- -p build",
            "sudo -E dotnet run myapp.dll -- -p build",
            "sudo dotnet publish",
            "MY_ENV_VAR=build dotnet myapp.dll",
        ],
    }

    builtin_commands_not_injected = [
        "ps -fea",
        "touch myfile.txt",
        "hello=hola cat myfile.txt",
        "ls -la",
        "mkdir newdir",
    ]

    @parametrize_virtual_machines(
        bugs=[
            {"vm_branch": "amazon_linux2", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_branch": "centos_7_amd64", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_branch": "redhat", "vm_cpu": "arm64", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_name": "Ubuntu_24_10_amd64", "weblog_variant": "test-app-python", "reason": "INPLAT-478"},
            {"vm_name": "Ubuntu_24_10_arm64", "weblog_variant": "test-app-python", "reason": "INPLAT-478"},
        ]
    )
    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_builtIn_block_commands(self, virtual_machine):
        """Check that commands are skipped from the auto injection. This commands are defined on the buildIn processes to block"""
        logger.info(f"[{virtual_machine.get_ip()}] Executing commands that should be blocked")
        ssh_client = virtual_machine.ssh_config.get_ssh_connection()
        for command in self.builtin_commands_not_injected:
            local_log_file = self._execute_remote_command(ssh_client, command)
            assert command_injection_skipped(command, local_log_file), f"The command {command} was instrumented!"

    @parametrize_virtual_machines(
        bugs=[
            {"vm_branch": "amazon_linux2", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_branch": "centos_7_amd64", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_branch": "redhat", "vm_cpu": "arm64", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_name": "Ubuntu_24_10_amd64", "weblog_variant": "test-app-python", "reason": "INPLAT-478"},
            {"vm_name": "Ubuntu_24_10_arm64", "weblog_variant": "test-app-python", "reason": "INPLAT-478"},
        ]
    )
    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_builtIn_block_args(self, virtual_machine):
        """Check that we are blocking command with args. These args are defined in the buildIn args ignore list for each language."""
        logger.info(f"[{virtual_machine.get_ip()}] Executing test_builtIn_block_args")
        language = context.scenario.library.library
        if language in self.builtin_args_commands_block:
            ssh_client = virtual_machine.ssh_config.get_ssh_connection()
            for command in self.builtin_args_commands_block[language]:
                local_log_file = self._execute_remote_command(ssh_client, command)
                assert command_injection_skipped(command, local_log_file), f"The command {command} was instrumented!"

    @parametrize_virtual_machines(
        bugs=[
            {"vm_branch": "amazon_linux2", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_branch": "centos_7_amd64", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_branch": "redhat", "vm_cpu": "arm64", "library": "ruby", "reason": "INPLAT-103"},
            {"vm_name": "Ubuntu_24_10_amd64", "weblog_variant": "test-app-python", "reason": "INPLAT-478"},
            {"vm_name": "Ubuntu_24_10_arm64", "weblog_variant": "test-app-python", "reason": "INPLAT-478"},
        ]
    )
    @irrelevant(
        condition="container" in context.weblog_variant
        or "alpine" in context.weblog_variant
        or "buildpack" in context.weblog_variant
    )
    def test_builtIn_instrument_args(self, virtual_machine):
        """Check that we are instrumenting the command with args that it should be instrumented. The args are not included on the buildIn args list"""
        logger.info(f"[{virtual_machine.get_ip()}] Executing test_builtIn_instrument_args")
        language = context.scenario.library.library
        if language in self.builtin_args_commands_injected:
            ssh_client = virtual_machine.ssh_config.get_ssh_connection()
            for command in self.builtin_args_commands_injected[language]:
                local_log_file = self._execute_remote_command(ssh_client, command)
                assert (
                    command_injection_skipped(command, local_log_file) is False
                ), f"The command {command} was not instrumented, but it should be instrumented!"
