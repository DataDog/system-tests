import os

import pytest
import json

from utils import scenarios, context, features
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port

import paramiko
from scp import SCPClient
from utils.onboarding.pulumi_ssh import PulumiSSH


class _OnboardingInstallBaseTest:
    def test_for_traces(self, onboardig_vm):
        """ We can easily install agent and lib injection software from agent installation script. Given a  sample application we can enable tracing using local environment variables.  
            After starting application we can see application HTTP requests traces in the backend.
            Using the agent installation script we can install different versions of the software (release or beta) in different OS."""

        logger.info(f"Launching test for : [{onboardig_vm.ip}]")
        logger.info(f"Waiting for weblog available [{onboardig_vm.ip}]")
        # TODO move this wait command to the scenario warmup. How to do this? Pulumi is working in parallel and async, in the scenario warmup we don't have the server IP
        wait_for_port(5985, onboardig_vm.ip, 80.0)
        logger.info(f"[{onboardig_vm.ip}]: Weblog app is ready!")
        logger.info(f"Making a request to weblog [{onboardig_vm.ip}]")
        request_uuid = make_get_request("http://" + onboardig_vm.ip + ":5985/")
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{onboardig_vm.ip}]")
        wait_backend_trace_id(request_uuid, 60.0)


class _OnboardingUninstallBaseTest:
    def test_no_traces_after_uninstall(self, onboardig_vm):
        logger.info(f"Launching uninstallation test for : [{onboardig_vm.ip}]")
        logger.info(f"Waiting for weblog available [{onboardig_vm.ip}]")
        # We uninstalled the autoinjection software, but the application should work
        wait_for_port(5985, onboardig_vm.ip, 60.0)
        logger.info(f"Making a request to weblog [{onboardig_vm.ip}]")
        request_uuid = make_get_request("http://" + onboardig_vm.ip + ":5985/")
        logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{onboardig_vm.ip}]")
        try:
            wait_backend_trace_id(request_uuid, 10.0)
            raise AssertionError("The weblog application is instrumented after uninstall DD software")
        except TimeoutError:
            # OK there are no traces, the weblog app is not instrumented
            pass


@features.container_auto_instrumentation
@scenarios.onboarding_container_install_manual
class TestOnboardingInstallManualContainer(_OnboardingInstallBaseTest):
    pass


@features.host_auto_instrumentation
@scenarios.onboarding_host_install_manual
class TestOnboardingInstallManualHost(_OnboardingInstallBaseTest):
    pass


@features.host_auto_instrumentation
@scenarios.onboarding_host_install_script
class TestOnboardingInstallScriptHost(_OnboardingInstallBaseTest):
    pass


@features.container_auto_instrumentation
@scenarios.onboarding_container_install_script
class TestOnboardingInstallScriptContainer(_OnboardingInstallBaseTest):
    pass


#########################
# Uninstall scenarios
#########################


@features.container_auto_instrumentation
@scenarios.onboarding_container_uninstall
class TestOnboardingUninstallContainer(_OnboardingUninstallBaseTest):
    pass


@features.host_auto_instrumentation
@scenarios.onboarding_host_uninstall
class TestOnboardingUninstallHost(_OnboardingUninstallBaseTest):
    pass


#########################
# Block list scenarios
#########################
class _OnboardingBlockListBaseTest:
    all_command_lines = []

    def _ssh_connect(self, ip, user):
        """ Establish the connection with the remote machine """
        cert = paramiko.RSAKey.from_private_key_file(PulumiSSH.pem_file)
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname=ip, username=user, pkey=cert)
        return ssh_client

    def _parse_remote_log_file(self, ssh_client):
        """ Get remote log file from the vm and parse it """
        scp = SCPClient(ssh_client.get_transport())
        scp.get(
            remote_path="/opt/datadog/logs_injection/host_injection.log",
            local_path=scenarios.onboarding_host_block_list.host_log_folder + "/host_injection.log",
        )

        store_as_command = False
        command_lines = []
        with open("logs_onboarding_host_block_list/host_injection.log") as f:
            for line in f:
                if "starting process" in line:
                    store_as_command = True
                    continue
                if "exiting process" in line:
                    store_as_command = False
                    self.all_command_lines.insert(0, command_lines.copy())
                    command_lines = []
                    continue

                if store_as_command:
                    command_lines.append(line)

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

    def _check_command_skipped(self, command):
        """ From parsed log, search on the list of logged commands if one command has been skipped from the instrumentation"""
        command_args = command.split()
        command = command_args[0]

        logger.info(f"- Checking command: {command_args}")
        for command_desc in self.all_command_lines:
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
        logger.info(f"    Command {command} was NOT skipped")
        return False


@features.host_auto_instrumentation
@scenarios.onboarding_host_block_list
class TestOnboardingBlockListInstallManualHost(_OnboardingBlockListBaseTest):
    def test_for_traces(self, onboardig_vm):
        ssh_client = self._ssh_connect(onboardig_vm.ip, onboardig_vm.ec2_data["user"])

        # Execute commands
        ssh_client.exec_command("ps -fea")
        ssh_client.exec_command("touch myfile.txt")
        ssh_client.exec_command("cat myfile.txt")
        ssh_client.exec_command("ls -la")
        ssh_client.exec_command("java -version")
        ssh_client.exec_command("java -help")

        # Check if the previously launched commands are skipped from the instrumentation
        self._parse_remote_log_file(ssh_client)

        assert self._check_command_skipped("ps -fea")
        assert self._check_command_skipped("touch myfile.txt")
        assert self._check_command_skipped("cat myfile.txt")
        assert self._check_command_skippedd("ls -la")
        assert self._check_command_skipped("java -version")
        assert not self._check_command_skipped("java -help")
