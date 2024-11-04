import os
import time
import pytest
import paramiko
from utils.tools import logger
from utils.onboarding.weblog_interface import make_get_request, simple_request, warmup_weblog, make_internal_get_request
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils.virtual_machine.vm_logger import vm_logger
from utils import context
from threading import Timer


class AutoInjectBaseTest:
    def _test_install(self, virtual_machine, profile: bool = False):
        """ We can easily install agent and lib injection software from agent installation script. Given a  sample application we can enable tracing using local environment variables.
            After starting application we can see application HTTP requests traces in the backend.
            Using the agent installation script we can install different versions of the software (release or beta) in different OS."""
        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        header = "----------------------------------------------------------------------"
        vm_logger(context.scenario.name, virtual_machine.name).info(
            f"{header} \n {header}  \n  Launching the install for VM: {virtual_machine.name}  \n {header} \n {header}"
        )
        request_uuids = []
        if virtual_machine.krunvm_config is not None and virtual_machine.krunvm_config.stdin is not None:
            logger.info(
                f"We are testing on krunvm. The request to the weblog will be done using the stdin (inside the microvm)"
            )
            request_uuids.append(make_internal_get_request(virtual_machine.krunvm_config.stdin, vm_port))
        else:
            logger.info(f"Waiting for weblog available [{vm_ip}:{vm_port}]")
            wait_for_port(vm_port, vm_ip, 80.0)
            logger.info(f"[{vm_ip}]: Weblog app is ready!")
            responseJson = warmup_weblog(f"http://{vm_ip}:{vm_port}/")
            if responseJson is not None:
                logger.info(f"There is a multicontainer app: {responseJson}")
                for app in responseJson["apps"]:
                    warmup_weblog(f"http://{vm_ip}:{vm_port}{app['url']}")
                    logger.info(f"Making a request to weblog [http://{vm_ip}:{vm_port}{app['url']}]")
                    request_uuids.append(make_get_request(f"http://{vm_ip}:{vm_port}{app['url']}"))
                    time.sleep(1)
            else:
                logger.info(f"Making a request to weblog [{vm_ip}:{vm_port}]")
                request_uuids.append(make_get_request(f"http://{vm_ip}:{vm_port}/"))

        for request_uuid in request_uuids:
            logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{vm_ip}]")
            wait_backend_trace_id(request_uuid, 120.0, profile=profile)
            # Some flakyness here: Sometimes the tracers are not in the backend.
            # Sometimes the backend respose with 429 (too many requests)
            # Not clear if this fix this issue
            time.sleep(1)

    def warmup(self, virtual_machine):
        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        warmup_weblog(f"http://{vm_ip}:{vm_port}/")

    def get_commandline(self, virtual_machine) -> int:
        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        return simple_request(f"http://{vm_ip}:{vm_port}/commandline", swallow=False)

    def fork_and_crash(self, virtual_machine) -> int:
        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        return simple_request(f"http://{vm_ip}:{vm_port}/fork_and_crash", swallow=False)

    def close_channel(self, channel):
        try:
            if not channel.eof_received:
                channel.close()
        except Exception as e:
            logger.error(f"Error closing the channel: {e}")

    def execute_command(self, virtual_machine, command) -> str:
        # Env for the command
        prefix_env = ""
        for key, value in virtual_machine.get_command_environment().items():
            prefix_env += f"export {key}={value} \n"

        command_with_env = f"{prefix_env} {command}"

        with virtual_machine.ssh_config.get_ssh_connection() as ssh:
            timeout = 120

            _, stdout, _ = ssh.exec_command(command_with_env, timeout=timeout + 5)
            stdout.channel.set_combine_stderr(True)

            # Enforce that even if we reach the 2min mark we can still have a partial output of the command
            # and thus see where it is stuck.
            Timer(timeout, self.close_channel, (stdout.channel,)).start()

            # Read the output line by line
            command_output = ""
            for line in stdout.readlines():
                if not line.startswith("export"):
                    command_output += line
            header = "*****************************************************************"
            vm_logger(context.scenario.name, virtual_machine.name).info(
                f"{header} \n  - COMMAND:  \n {header} \n {command} \n\n {header} \n COMMAND OUTPUT \n\n {header} \n {command_output}"
            )

            return command_output

    def _test_uninstall_commands(
        self, virtual_machine, stop_weblog_command, start_weblog_command, uninstall_command, install_command
    ):
        """ We can unistall the auto injection software. We can start the app again
        The weblog app should work but no sending traces to the backend.
        We can reinstall the auto inject software. The weblog app should be instrumented
        and reporting traces to the backend."""
        logger.info(f"Launching _test_uninstall for : [{virtual_machine.name}]")

        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        weblog_url = f"http://{vm_ip}:{vm_port}/"

        # Kill the app before the uninstallation
        logger.info(f"[Uninstall {virtual_machine.name}] Stop app")
        self.execute_command(virtual_machine, stop_weblog_command)
        logger.info(f"[Uninstall {virtual_machine.name}] Stop app done")
        # Uninstall the auto inject
        logger.info(f"[Uninstall {virtual_machine.name}] Uninstall command")
        self.execute_command(virtual_machine, uninstall_command)
        logger.info(f"[Uninstall {virtual_machine.name}] Uninstall command done")
        # Start the app again
        logger.info(f"[Uninstall {virtual_machine.name}] Start app")
        self.execute_command(virtual_machine, start_weblog_command)
        logger.info(f"[Uninstall {virtual_machine.name}] Start app done")

        request_uuids = []
        wait_for_port(vm_port, vm_ip, 40.0)
        responseJson = warmup_weblog(f"http://{vm_ip}:{vm_port}/")
        if responseJson is not None:
            logger.info(f"There is a multicontainer app: {responseJson}")
            for app in responseJson["apps"]:
                logger.info(f"Making a request to weblog [http://{vm_ip}:{vm_port}{app['url']}]")
                request_uuids.append(make_get_request(f"http://{vm_ip}:{vm_port}{app['url']}"))
        else:
            logger.info(f"Making a request to weblog [weblog_url]")
            request_uuids.append(make_get_request(weblog_url))

        try:
            for request_uuid in request_uuids:
                logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{vm_ip}]")
                wait_backend_trace_id(request_uuid, 10.0)
                raise AssertionError("The weblog application is instrumented after uninstall DD software")
        except TimeoutError:
            # OK there are no traces, the weblog app is not instrumented
            pass

        # Kill the app before restore the installation
        logger.info(f"[Uninstall {virtual_machine.name}] Stop app before restore")
        self.execute_command(virtual_machine, stop_weblog_command)
        logger.info(f"[Uninstall {virtual_machine.name}] Stop app before restore done")
        # reinstall the auto inject
        logger.info(f"[Uninstall {virtual_machine.name}] Reinstall dd ssi")
        self.execute_command(virtual_machine, install_command)
        logger.info(f"[Uninstall {virtual_machine.name}] Reinstall dd ssi done")
        # Start the app again
        logger.info(f"[Uninstall {virtual_machine.name}] Start app after reinstall dd ssi")
        self.execute_command(virtual_machine, start_weblog_command)
        logger.info(f"[Uninstall {virtual_machine.name}] Start app after reinstall dd ssi done")
        # The app should be instrumented and reporting traces to the backend
        self._test_install(virtual_machine)
        logger.info(f"Success _test_uninstall for : [{virtual_machine.name}]")

    def _test_uninstall(self, virtual_machine):
        header = "----------------------------------------------------------------------"
        vm_logger(context.scenario.name, virtual_machine.name).info(
            f"{header} \n {header}  \n  Launching the uninstall for VM: {virtual_machine.name}  \n {header} \n {header}"
        )
        if context.weblog_variant == f"test-app-{context.scenario.library.library}":  # Host

            stop_weblog_command = "sudo systemctl kill -s SIGKILL test-app.service"
            start_weblog_command = "sudo systemctl start test-app.service"
            if context.scenario.library.library in ["ruby", "python", "dotnet"]:
                start_weblog_command = virtual_machine._vm_provision.weblog_installation.remote_command
        else:  # Container
            stop_weblog_command = "sudo -E docker-compose -f docker-compose.yml down"
            #   On older Docker versions, the network recreation can hang. The solution is to restart Docker.
            #   https://github.com/docker-archive/classicswarm/issues/1931
            start_weblog_command = "sudo systemctl restart docker && sudo -E docker-compose -f docker-compose.yml up --wait --wait-timeout 120"

        install_command = "sudo datadog-installer apm instrument"
        uninstall_command = "sudo datadog-installer apm uninstrument"
        self._test_uninstall_commands(
            virtual_machine, stop_weblog_command, start_weblog_command, uninstall_command, install_command
        )
