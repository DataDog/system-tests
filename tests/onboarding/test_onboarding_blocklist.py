import json
import uuid

from utils import scenarios, context, features
from utils.tools import logger

import paramiko
from scp import SCPClient
from utils.onboarding.pulumi_ssh import PulumiSSH
from utils import irrelevant
from utils.onboarding.injection_log_parser import command_injection_skipped


class _OnboardingBlockListBaseTest:
    """ Base class to test the block list on auto instrumentation"""

    def _ssh_connect(self, ip, user):
        """ Establish the connection with the remote machine """
        cert = paramiko.RSAKey.from_private_key_file(PulumiSSH.pem_file)
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=ip, username=user, pkey=cert)
        return ssh_client

    def _execute_remote_command(self, ssh_client, command, configEnv=None):
        """ Get remote log file from the vm  """

        unique_log_name = f"host_injection_{uuid.uuid4()}.log"
        command_with_config = (
            f"DD_APM_INSTRUMENTATION_OUTPUT_PATHS=/opt/datadog/logs_injection/{unique_log_name} {command}"
        )
        logger.info(f"Executing command: [{command}] associated with log file: [{unique_log_name}]")

        log_local_path = scenarios.onboarding_host_block_list.host_log_folder + f"/{unique_log_name}"

        ssh_client.exec_command(command_with_config)

        scp = SCPClient(ssh_client.get_transport())

        scp.get(
            remote_path=f"/opt/datadog/logs_injection/{unique_log_name}", local_path=log_local_path,
        )
        return log_local_path


@features.host_auto_instrumentation
@scenarios.onboarding_host_block_list
class TestOnboardingBlockListInstallManualHost(_OnboardingBlockListBaseTest):

    buildIn_args_commands_block = {
        "java": ["java -version", "MY_ENV_VAR=hello java -version"],
        "donet": [
            "dotnet restore",
            "dotnet build -c Release",
            "sudo -E dotnet publish",
            "MY_ENV_VAR=hello dotnet build -c Release",
        ],
    }

    buildIn_args_commands_injected = {
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

    buildIn_commands_not_injected = [
        "ps -fea",
        "touch myfile.txt",
        "hello=hola cat myfile.txt",
        "ls -la",
        "mkdir newdir",
    ]

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_block_commands(self, onboardig_vm):
        """ Check that commands are skipped from the auto injection. This commands are defined on the buildIn processes to block """

        ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])

        for command in self.buildIn_commands_not_injected:
            local_log_file = self._execute_remote_command(ssh_client, command)
            assert command_injection_skipped(command, local_log_file), f"The command {command} was instrumented!"

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_block_args(self, onboardig_vm):
        """ Check that we are blocking command with args. These args are defined in the buildIn args ignore list for each language."""

        if onboardig_vm.language in self.buildIn_args_commands_block:
            ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])
            for command in self.buildIn_args_commands_block[onboardig_vm.language]:
                local_log_file = self._execute_remote_command(ssh_client, command)
                assert command_injection_skipped(command, local_log_file), f"The command {command} was instrumented!"

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_instrument_args(self, onboardig_vm):
        """ Check that we are instrumenting the command with args that it should be instrumented. The args are not included on the buildIn args list"""

        if onboardig_vm.language in self.buildIn_args_commands_injected:
            ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])
            for command in self.buildIn_args_commands_injected[onboardig_vm.language]:
                local_log_file = self._execute_remote_command(ssh_client, command)
                assert False == command_injection_skipped(
                    command, local_log_file
                ), f"The command {command} was not instrumented, but it should be instrumented!"

    def _create_remote_executable_script(self, ssh_client, script_path, content="#!/bin/bash \\n echo 'Hey!'"):
        ssh_client.exec_command(f"sudo sh -c 'echo \"${content}\" > {script_path}' && sudo chmod 755 {script_path}")

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_user_ignored_processes(self, onboardig_vm):
        """ Check that we are not instrumenting the commands that match with patterns set by DD_IGNORED_PROCESSES env variable"""

        ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])
        # Create a simple executable script
        self._create_remote_executable_script(ssh_client, "/opt/datadog/logs_injection/myscript.sh")

        execute_command = """ 
        DD_IGNORED_PROCESSES="/opt/datadog/logs_injection/*,other" /opt/datadog/logs_injection/myscript.sh
        """

        # Retrieve the log file
        local_log_file = self._execute_remote_command(ssh_client, execute_command)

        assert command_injection_skipped(
            execute_command, local_log_file
        ), f"The command {execute_command} was instrumented, but it's defined on the user block list!"
