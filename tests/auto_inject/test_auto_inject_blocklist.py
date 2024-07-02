import json
import uuid

from utils import scenarios, context, features
from utils.tools import logger

import paramiko
from scp import SCPClient
from utils import irrelevant
from utils.onboarding.injection_log_parser import command_injection_skipped


class _AutoInjectBlockListBaseTest:
    """ Base class to test the block list on auto instrumentation"""

    env_vars_config_mapper = {
        "java": "DD_JAVA_IGNORED_ARGS",
        "dotnet": "DD_DOTNET_IGNORED_ARGS",
        "python": "DD_PYTHON_IGNORED_ARGS",
        "nodejs": "DD_NODE_IGNORED_ARGS",
        "ruby": "DD_RUBY_IGNORED_ARGS",
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
ignored_arguments:
    Java:
        - DD_JAVA_IGNORED_ARGS
    DotNet:
        - DD_DOTNET_IGNORED_ARGS
    Python:
        - DD_PYTHON_IGNORED_ARGS
    Node:
        - DD_NODE_IGNORED_ARGS
    Ruby:
        - DD_RUBY_IGNORED_ARGS
"""

    def _execute_remote_command(self, ssh_client, command, config={}, use_injection_config=False):
        """ Execute remote command and get remote log file from the vm. You can use this method using env variables or using injection config file  """

        unique_log_name = f"host_injection_{uuid.uuid4()}.log"

        command_with_config = (
            f"DD_APM_INSTRUMENTATION_OUTPUT_PATHS=/opt/datadog/logs_injection/{unique_log_name} {command}"
        )
        if use_injection_config:
            # Use yml template and replace the key DD_<lang>_IGNORED_ARGS with the value of the config
            test_conf_content = self.yml_config_template
            for key in config:
                config_values = ""
                for conf_val in config[key].split(","):
                    # Fix the indentation
                    if config_values == "":
                        config_values = "- '" + conf_val + "'\n"
                    else:
                        config_values = config_values + "        - '" + conf_val + "'\n"
                test_conf_content = test_conf_content.replace("- " + key, config_values)

            # Write as local file and the copy by scp to user home. by ssh copy the file to /etc/datadog-agent/inject
            file_name = f"host_config_{uuid.uuid4()}.yml"
            temp_file_path = scenarios.host_auto_injection_block_list.host_log_folder + "/" + file_name
            with open(temp_file_path, "w") as host_config_file:
                host_config_file.write(test_conf_content)
            SCPClient(ssh_client.get_transport()).put(temp_file_path, file_name)
            logger.info(f"Using config {file_name}")
            # Copy config file and read out to force wait command execution
            _, stdout, stderr = ssh_client.exec_command(
                f"sudo cp {file_name} /etc/datadog-agent/inject/host_config.yaml"
            )
            stdout.channel.set_combine_stderr(True)
            output = stdout.readlines()
        else:
            # We'll use env variables instead of injection config yml
            for key in config:
                command_with_config = f"{key}='{config[key]}' {command_with_config}"

        logger.info(f"Executing command: [{command_with_config}] associated with log file: [{unique_log_name}]")

        log_local_path = scenarios.host_auto_injection_block_list.host_log_folder + f"/{unique_log_name}"

        _, stdout, stderr = ssh_client.exec_command(command_with_config)
        logger.info("Command output:")
        logger.info(stdout.readlines())
        logger.info("Command err output:")
        logger.info(stderr.readlines())

        scp = SCPClient(ssh_client.get_transport())

        scp.get(
            remote_path=f"/opt/datadog/logs_injection/{unique_log_name}", local_path=log_local_path,
        )
        return log_local_path


@features.host_user_managed_block_list
@scenarios.host_auto_injection_block_list
class TestAutoInjectBlockListInstallManualHost(_AutoInjectBlockListBaseTest):

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
            {
                "ignored_args": "-Dtest3=test2",
                "command": "java -jar test.jar -Dtest2=test2 -Dtest=test",
                "skip": False,
            },
        ],
        "dotnet": [
            {"ignored_args": "/Users/user/Pictures", "command": "dotnet run -- -p /Users/user/Pictures", "skip": True},
            {
                "ignored_args": "/Users/user/PicturesXXX",
                "command": "dotnet run -- -p /Users/user/Pictures",
                "skip": False,
            },
            {
                "ignored_args": "/MySetting:SomeValue=123",
                "command": "dotnet run /MySetting:SomeValue=123",
                "skip": True,
            },
        ],
        "python": [
            {
                "ignored_args": "",
                "command": "/home/datadog/.pyenv/shims/python myscript.py arg1 arg2 arg3",
                "skip": False,
            },
            {
                "ignored_args": "arg1",
                "command": "/home/datadog/.pyenv/shims/python myscript.py arg1 arg2 arg3",
                "skip": True,
            },
            {
                "ignored_args": "arg12,arg2,arg44",
                "command": "/home/datadog/.pyenv/shims/python myscript.py arg1 arg2 arg3",
                "skip": True,
            },
            {
                "ignored_args": "arg11, arg22,arg44",
                "command": "/home/datadog/.pyenv/shims/python myscript.py arg1 arg2 arg3",
                "skip": False,
            },
            {
                "ignored_args": "--dosomething",
                "command": "/home/datadog/.pyenv/shims/python myscript.py --dosomething yes",
                "skip": True,
            },
            {
                "ignored_args": "--dosomethingXXXX",
                "command": "/home/datadog/.pyenv/shims/python myscript.py --dosomething no",
                "skip": False,
            },
        ],
        "nodejs": [
            {"ignored_args": "", "command": "node example.js -a -b -c", "skip": False},
            {"ignored_args": "-c", "command": "node example.js -a -b -c", "skip": True},
            {"ignored_args": "", "command": "node example.js -f --custom Override", "skip": False},
            {"ignored_args": "--custom", "command": "node example.js -f --custom Override", "skip": True},
        ],
        "ruby": [
            {"ignored_args": "", "command": "ruby my_cat.rb test1 test2", "skip": False},
            {"ignored_args": "test1", "command": "ruby my_cat.rb test1 test2", "skip": True},
            {"ignored_args": "test3,test2", "command": "ruby my_cat.rb test1 test2", "skip": True},
            {"ignored_args": "test1,test2", "command": "ruby names.rb --name pepe", "skip": False},
            {"ignored_args": "--name", "command": "ruby names.rb --name pepe", "skip": True},
            {
                "ignored_args": "",
                "command": "bundle config build.pg --with-pg-config=/path/to/pg_config",
                "skip": False,
            },
            {
                "ignored_args": "--with-pg-config",
                "command": "bundle config build.pg --with-pg-config=/path/to/pg_config",
                "skip": False,
            },
            {
                "ignored_args": "--with-pg-config=/path/to/pg_config",
                "command": "bundle config build.pg --with-pg-config=/path/to/pg_config",
                "skip": True,
            },
            {
                "ignored_args": "--with-pg-config=/home/to/pg_config",
                "command": "bundle config build.pg --with-pg-config=/path/to/pg_config",
                "skip": False,
            },
        ],
    }

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_block_commands(self, virtual_machine):
        """ Check that commands are skipped from the auto injection. This commands are defined on the buildIn processes to block """

        ssh_client = virtual_machine.ssh_config.get_ssh_connection()

        for command in self.buildIn_commands_not_injected:
            local_log_file = self._execute_remote_command(ssh_client, command)
            assert command_injection_skipped(command, local_log_file), f"The command {command} was instrumented!"

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_block_args(self, virtual_machine):
        """ Check that we are blocking command with args. These args are defined in the buildIn args ignore list for each language."""
        language = context.scenario.library.library
        if language in self.buildIn_args_commands_block:
            ssh_client = virtual_machine.ssh_config.get_ssh_connection()
            for command in self.buildIn_args_commands_block[language]:
                local_log_file = self._execute_remote_command(ssh_client, command)
                assert command_injection_skipped(command, local_log_file), f"The command {command} was instrumented!"

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_builtIn_instrument_args(self, virtual_machine):
        """ Check that we are instrumenting the command with args that it should be instrumented. The args are not included on the buildIn args list"""
        language = context.scenario.library.library
        if language in self.buildIn_args_commands_injected:
            ssh_client = virtual_machine.ssh_config.get_ssh_connection()
            for command in self.buildIn_args_commands_injected[language]:
                local_log_file = self._execute_remote_command(ssh_client, command)
                assert False == command_injection_skipped(
                    command, local_log_file
                ), f"The command {command} was not instrumented, but it should be instrumented!"

    def _create_remote_executable_script(self, ssh_client, script_path, content="#!/bin/bash \\n echo 'Hey!'"):
        _, stdout, stderr = ssh_client.exec_command(
            f"sudo sh -c 'echo \"${content}\" > {script_path}' && sudo chmod 755 {script_path}"
        )
        stdout.channel.set_combine_stderr(True)
        output = stdout.readlines()

    @irrelevant(
        condition="datadog-apm-inject" not in context.scenario.components
        or context.scenario.components["datadog-apm-inject"] < "0.12.4",
        reason="Block list not fully implemented ",
    )
    def test_user_ignored_args(self, virtual_machine):
        """ Check that we are not instrumenting the lang commands (java,ruby,dotnet,python) that match with args set by DD_<LANG>_IGNORED_ARGS env variable"""
        language = context.scenario.library.library
        if language in self.user_args_commands:
            ssh_client = virtual_machine.ssh_config.get_ssh_connection()
            for test_config in self.user_args_commands[language]:
                for use_injection_file_config in [True, False]:
                    # Apply the configuration from yml file or from env variables
                    language_ignored_args_key = self.env_vars_config_mapper[language]
                    args_config = {language_ignored_args_key: test_config["ignored_args"]}
                    local_log_file = self._execute_remote_command(
                        ssh_client,
                        test_config["command"],
                        config=args_config,
                        use_injection_config=use_injection_file_config,
                    )
                    assert test_config["skip"] == command_injection_skipped(
                        test_config["command"], local_log_file
                    ), f"The command {test_config['command']} with ignored args {test_config['ignored_args']} should skip [{test_config['skip']}]!"
