import json
import uuid

from utils import scenarios, context, features
from utils.tools import logger

import paramiko
from scp import SCPClient
from utils.onboarding.pulumi_ssh import PulumiSSH
from utils import irrelevant


class _OnboardingBlockListBaseTest:
    """ Base class to test the block list on auto instrumentation"""

    def _ssh_connect(self, ip, user):
        """ Establish the connection with the remote machine """
        cert = paramiko.RSAKey.from_private_key_file(PulumiSSH.pem_file)
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=ip, username=user, pkey=cert)
        return ssh_client

    def _parse_remote_log_file(self, ssh_client):
        """ Get remote log file from the vm and parse it """
        log_local_name_uuid = uuid.uuid4()
        log_local_path = (
            scenarios.onboarding_host_block_list.host_log_folder + f"/host_injection{log_local_name_uuid}.log"
        )
        all_command_lines = []
        scp = SCPClient(ssh_client.get_transport())

        scp.get(
            remote_path="/opt/datadog/logs_injection/host_injection.log", local_path=log_local_path,
        )

        store_as_command = False
        command_lines = []
        with open(log_local_path) as f:
            for line in f:
                if "starting process" in line:
                    store_as_command = True
                    continue
                if "exiting process" in line:
                    store_as_command = False
                    all_command_lines.insert(0, command_lines.copy())
                    command_lines = []
                    continue

                if store_as_command:
                    command_lines.append(line)
        return all_command_lines

    def _get_command_props_values(self, command_instrumentation_desc, command_args_check):
        """ Search into command_instrumentation_desc (lines related with the command on the log file) if the command and arguments are equal 
            The line that contains the command with args should be like this (example for java -help):
                {"level":"debug","ts":1,"caller":"xx","msg":"props values","props":{"Env":"","Service":"","Version":"","ProcessProps":{"Path":"/usr/bin/java","Args":["java","-help"]},"ContainerProps":{"Labels":null,"Name":"","ShortName":"","Tag":""}}}
        """
        for line in command_instrumentation_desc:
            if "props values" in line:
                line_json = json.loads(line)
                command_log_args = line_json["props"]["ProcessProps"]["Args"]
                command_compared_result = set(command_log_args) & set(command_args_check)
                is_same_command = len(command_log_args) == len(command_args_check) and len(
                    set(command_log_args) & set(command_args_check)
                ) == len(command_args_check)
                return is_same_command
        return False

    def _check_command_skipped(self, command, all_command_lines):
        """ From parsed log, search on the list of logged commands if one command has been skipped from the instrumentation"""
        command_args = command.split()
        command = None
        # Command could not be the first arg example "env_var=1 ./mycommand"
        for com in command_args:
            if "=" in com:
                continue
            command = com
            break

        logger.info(f"- Checking command: {command_args}")
        for command_desc in all_command_lines:
            # First line contains the name of the intercepted command
            first_line_json = json.loads(command_desc[0])
            if command in first_line_json["inFilename"]:
                # last line contains the skip message. The command was skipped by build-in deny list
                last_line_json = json.loads(command_desc[-1])
                if last_line_json["msg"] == "not injecting; on deny list":
                    logger.info(f"    Command {command_args} was skipped by build-in deny list")
                    return True
                # Perhaps the command was instrumented or could be skipped by its arguments. Checking
                elif self._get_command_props_values(command_desc, command_args) == True:
                    if last_line_json["msg"] == "error when parsing" and last_line_json["error"].startswith(
                        "skipping due to ignore rules for language"
                    ):
                        logger.info(f"    Command {command_args} was skipped by ignore arguments")
                        return True
                    else:
                        logger.info(f"    command {command_args} is found but it was instrumented!")
                        return False
        logger.info(f"    Command {command} was NOT FOUND")
        raise ValueError(f"Command {command} was NOT FOUND")


@features.host_auto_instrumentation
@scenarios.onboarding_host_block_list
class TestOnboardingBlockListInstallManualHost(_OnboardingBlockListBaseTest):

    commands_block = {
        "java": ["java -version", "MY_ENV_VAR=hello java -help"],
        "donet": [
            "dotnet restore",
            "dotnet build -c Release",
            "sudo dotnet publish",
            "MY_ENV_VAR=hello dotnet build -c Release",
        ],
    }

    commands_instrument = {
        "java": [
            "java -jar myjar.jar",
            "sudo java -jar myjar.jar",
            "version=-version java -jar myjar.jar",
            "java -Dversion='-version' -jar myapp.jar",
        ],
        "donet": [
            "dotnet run -- -p build",
            "dotnet build.dll -- -p build",
            "sudo dotnet run myapp.dll -- -p build",
            "sudo dotnet publish",
            "MY_ENV_VAR=build dotnet myapp.dll",
        ],
    }

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] <= "0.12.3",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_block_commands(self, onboardig_vm):
        """ Check that commands are skipped from the auto instrummentation"""

        ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])

        commands_not_instrument = [
            "ps -fea",
            "touch myfile.txt",
            "hello=hola cat myfile.txt",
            "ls -la",
            "mkdir newdir",
        ]

        for command in commands_not_instrument:
            ssh_client.exec_command(command)

        # Retrieve and parse the log file
        all_command_lines = self._parse_remote_log_file(ssh_client)

        for command in commands_not_instrument:
            assert self._check_command_skipped(command, all_command_lines), f"The command {command} was instrumented!"

    def _assert_commands_block(self, ssh_client, commands, should_block=True):
        """Assert that a command should be blocked or instrument."""
        for command in commands:
            ssh_client.exec_command(command)

        all_command_lines = self._parse_remote_log_file(ssh_client)

        for command in commands:
            assert should_block == self._check_command_skipped(
                command, all_command_lines
            ), f"Failed. The command {command} was instrumented"

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] <= "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_block_args(self, onboardig_vm):
        """ Check that we are blocking command with args that it should block"""
        if onboardig_vm.language in self.commands_block:
            ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])
            self._assert_commands_block(ssh_client, self.commands_block[onboardig_vm.language], should_block=True)

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] <= "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_instrument_args(self, onboardig_vm):
        """ Check that we are instrumenting the command with args that it should instrument"""
        if onboardig_vm.language in self.commands_instrument:
            ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])
            self._assert_commands_block(ssh_client, self.commands_instrument[onboardig_vm.language], should_block=False)

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] <= "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_user_ignored_processes_args(self, onboardig_vm):
        """ Check that we are not instrumenting the commands that match with patterns set by DD_IGNORED_PROCESSES env variable"""

        ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])
        command = "test.sh"
        ssh_client.exec_command(command)
        # Retrieve and parse the log file
        all_command_lines = self._parse_remote_log_file(ssh_client)
        assert self._check_command_skipped(command, all_command_lines), f"The command {command} was instrumented!"
