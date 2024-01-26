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

    env_vars_config_file_mapper = {
        "DD_JAVA_IGNORED_ARGS": "java_ignored_args",
        "DD_IGNORED_PROCESSES": "ignored_processes",
    }

    yml_config_template = """
---
log_level: debug
output_paths:
  - file:///tmp/host_injection.log
env: dev
config_sources: BASIC
ignored_processes: 
- DD_IGNORED_PROCESSES
"""

    def _ssh_connect(self, ip, user):
        """ Establish the connection with the remote machine """
        cert = paramiko.RSAKey.from_private_key_file(PulumiSSH.pem_file)
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=ip, username=user, pkey=cert)
        return ssh_client

    def _execute_remote_command(self, ssh_client, command, config={}, use_injection_config=False):
        """ Execute remote command and get remote log file from the vm. You can use this method using env variables or using injection config file  """

        unique_log_name = f"host_injection_{uuid.uuid4()}.log"

        command_with_config = (
            f"DD_APM_INSTRUMENTATION_OUTPUT_PATHS=/opt/datadog/logs_injection/{unique_log_name} {command}"
        )
        if use_injection_config:
            test_conf_content = self.yml_config_template
            for key in config:
                config_values = ""
                for conf_val in config[key].split(","):
                    config_values = config_values + " - '" + conf_val + "'\n"
                test_conf_content = test_conf_content.replace("- " + key, config_values)

            # Write as local file and the copy by scp to user home. by ssh copy the file to /etc/datadog-agent/inject
            file_name = f"host_config_{uuid.uuid4()}.yml"
            temp_file_path = scenarios.onboarding_host_block_list.host_log_folder + "/" + file_name
            with open(temp_file_path, "w") as host_config_file:
                host_config_file.write(test_conf_content)
            SCPClient(ssh_client.get_transport()).put(temp_file_path, file_name)
            ssh_client.exec_command(f"sudo cp {file_name} /etc/datadog-agent/inject/host_config.yaml")
        else:
            # We'll use env variables instead of injection config yml
            for key in config:
                command_with_config = f"{key}={config[key]} {command_with_config}"

        logger.info(f"Executing command: [{command_with_config}] associated with log file: [{unique_log_name}]")

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

    user_args_commands = {
        "java": [
            {"ignored_args": "-Dtest=test", "command": "java -jar test.jar -Dtest=test", "skip": True},
            {
                "ignored_args": "one_param=1,-Dhey=hola,-Dtest=test",
                "command": "java -jar test.jar -Dtest=test",
                "skip": True,
            },
            {"ignored_args": "-Dtest=testXX", "command": "java -jar test.jar -Dtest=test", "skip": False},
        ],
    }

    user_processes_commands = [
        {
            "ignored_processes": "/opt/datadog/logs_injection/*,other",
            "command": "/opt/datadog/logs_injection/myscript.sh",
            "skip": True,
        },
        {"ignored_processes": "**/myscript.sh", "command": "/opt/datadog/logs_injection/myscript.sh", "skip": True},
        {
            "ignored_processes": "/opt/**/myscript.sh",
            "command": "/opt/datadog/logs_injection/myscript.sh",
            "skip": True,
        },
        {
            "ignored_processes": "myscript.sh,otherscript.sh",
            "command": "/opt/datadog/logs_injection/myscript.sh",
            "skip": False,
        },
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

        for test_config in self.user_processes_commands:
            for use_injection_file_config in [True, False]:
                # Apply the configuration from yml file or from env variables
                config_ignored_processes = {"DD_IGNORED_PROCESSES": test_config["ignored_processes"]}
                local_log_file = self._execute_remote_command(
                    ssh_client,
                    test_config["command"],
                    config=config_ignored_processes,
                    use_injection_config=use_injection_file_config,
                )

                assert test_config["skip"] == command_injection_skipped(
                    test_config["command"], local_log_file
                ), f"The command {test_config['command']} with config [{config_ignored_processes}] should be skip? [{test_config['skip']}]"

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_user_ignored_args(self, onboardig_vm):
        """ Check that we are not instrumenting the lang commands (java,ruby,dotnet,python) that match with args set by DD_<LANG>_IGNORED_ARGS env variable"""

        if onboardig_vm.language in self.user_args_commands:
            ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])
            for test_config in self.user_args_commands[onboardig_vm.language]:
                args_config = {"DD_JAVA_IGNORED_ARGS": test_config["ignored_args"]}
                local_log_file = self._execute_remote_command(ssh_client, test_config["command"], config=args_config)
                assert test_config["skip"] == command_injection_skipped(
                    test_config["command"], local_log_file
                ), f"The command {test_config['command']} with ignored args {test_config['ignored_args']} should skip [{test_config['skip']}]!"
