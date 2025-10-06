import time
from utils.onboarding.weblog_interface import make_get_request, warmup_weblog, make_internal_get_request
from utils.onboarding.backend_interface import wait_backend_trace_id
from utils.onboarding.wait_for_tcp_port import wait_for_port
from utils.virtual_machine.vm_logger import vm_logger
from utils import context, logger
from threading import Timer


class AutoInjectBaseTest:
    def _test_install(
        self, virtual_machine, *, profile: bool = False, appsec: bool = False, origin_detection: bool = False
    ):
        """If there is a multicontainer app, we need to make a request to each app"""

        if virtual_machine.get_deployed_weblog().app_type == "multicontainer":
            for app in virtual_machine.get_deployed_weblog().multicontainer_apps:
                vm_context_url = (
                    f"http://{virtual_machine.get_ip()}:{virtual_machine.deffault_open_port}{app.app_context_url}"
                )
                self._check_install(
                    virtual_machine, vm_context_url, profile=profile, appsec=appsec, origin_detection=origin_detection
                )

        else:
            vm_context_url = f"http://{virtual_machine.get_ip()}:{virtual_machine.deffault_open_port}{virtual_machine.get_deployed_weblog().app_context_url}"
            self._check_install(
                virtual_machine, vm_context_url, profile=profile, appsec=appsec, origin_detection=origin_detection
            )

    def _check_install(
        self,
        virtual_machine,
        vm_context_url,
        *,
        profile: bool = False,
        appsec: bool = False,
        origin_detection: bool = False,
    ):
        """We can easily install agent and lib injection software from agent installation script. Given a  sample application we can enable tracing using local environment variables.
        After starting application we can see application HTTP requests traces in the backend.
        Using the agent installation script we can install different versions of the software (release or beta) in different OS.
        """
        vm_ip = virtual_machine.get_ip()
        vm_port = virtual_machine.deffault_open_port
        header = "----------------------------------------------------------------------"
        vm_logger(context.scenario.host_log_folder, virtual_machine.name).info(
            f"{header} \n {header}  \n  Launching the install for VM: {virtual_machine.name}  \n {header} \n {header}"
        )
        if virtual_machine.krunvm_config is not None and virtual_machine.krunvm_config.stdin is not None:
            logger.info(
                "We are testing on krunvm. The request to the weblog will be done using the stdin (inside the microvm)"
            )
            request_uuid = make_internal_get_request(virtual_machine.krunvm_config.stdin, vm_port, appsec=appsec)
        else:
            logger.info(f"Waiting for weblog available [{vm_ip}:{vm_port}]")
            assert wait_for_port(vm_port, vm_ip, 80), "Weblog port not reachable. Is the weblog running?"
            logger.info(f"[{vm_ip}]: Weblog app is ready!")
            logger.info(f"Making a request to weblog [{vm_context_url}]")
            warmup_weblog(vm_context_url)
            request_uuid = make_get_request(vm_context_url, appsec=appsec)
            logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{vm_ip}]")

        validator = None
        if appsec:
            validator = self._appsec_validator
        if origin_detection:
            # TEMPORARY:  a delay see if that helps with container metadata is availability.
            logger.info("Waiting for container metadata to be available...")
            time.sleep(5)  # Increased from 1 to 5 seconds for container tag detection
            validator = self._container_tags_validator

        try:
            wait_backend_trace_id(request_uuid, profile=profile, validator=validator)
        except (TimeoutError, AssertionError) as e:
            self._log_trace_debug_message(e, request_uuid)
            raise

    def _appsec_validator(self, _, trace_data):
        """Validator for Appsec traces that checks if the trace contains an Appsec event."""
        root_id = trace_data["trace"]["root_id"]
        root_span = trace_data["trace"]["spans"][root_id]

        meta = root_span.get("meta", {})
        metrics = root_span.get("metrics", {})

        if "_dd.appsec.enabled" not in metrics or metrics["_dd.appsec.enabled"] != 1:
            logger.error(
                "expected '_dd.appsec.enabled' to be 1 in trace span metrics but found",
                metrics.get("_dd.appsec.enabled"),
            )
            return False

        if "appsec.event" not in meta or meta["appsec.event"] != "true":
            logger.error("expected 'appsec.event' to be true in trace meta but found", meta.get("appsec.event"))
            return False

        return True

    def _container_tags_validator(self, _, trace_data):
        root_id = trace_data["trace"]["root_id"]
        root_span = trace_data["trace"]["spans"][root_id]

        # Check if container tags exist in the trace metadata
        meta = root_span.get("meta", {})
        container_tags = meta.get("_dd.tags.container")

        if container_tags:
            logger.info(f"Found container tags: {container_tags}")
            return True
        else:
            logger.error(f"No container tags found in trace. Available meta keys: {list(meta.keys())}")
            return False

    def _log_trace_debug_message(self, exc: Exception, request_uuid: str) -> None:
        logger.error(
            f"❌ Exception during trace in backend verification: {exc}\n"
            "🔍 Possible causes:\n"
            "- A bug/problem in the tracer (check app logs in `/var/log/datadog_weblog`)\n"
            "- A problem in the agent (check agent logs in `/var/log/datadog`)\n"
            "- A problem in the Docker daemon?? (check logs in `/var/log/journalctl_docker.log`)\n"
            f"- A problem processing the intake in the backend (manually locate the trace id [{request_uuid}] in the DD console, using the system-tests organization)\n"
        )

    def close_channel(self, channel) -> None:
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

        with virtual_machine.get_ssh_connection() as ssh:
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
            vm_logger(context.scenario.host_log_folder, virtual_machine.name).info(
                f"{header} \n  - COMMAND:  \n {header} \n {command} \n\n {header} \n COMMAND OUTPUT \n\n {header} \n {command_output}"
            )

            return command_output

    def _test_uninstall_commands(
        self, virtual_machine, stop_weblog_command, start_weblog_command, uninstall_command, install_command
    ):
        """We can unistall the auto injection software. We can start the app again
        The weblog app should work but no sending traces to the backend.
        We can reinstall the auto inject software. The weblog app should be instrumented
        and reporting traces to the backend.
        """
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
        assert wait_for_port(vm_port, vm_ip, 40.0), "Weblog port not reachable. Is the weblog running?"
        response_json = warmup_weblog(f"http://{vm_ip}:{vm_port}/")
        if response_json is not None:
            logger.info(f"There is a multicontainer app: {response_json}")
            for app in response_json["apps"]:
                logger.info(f"Making a request to weblog [http://{vm_ip}:{vm_port}{app['url']}]")
                request_uuids.append(make_get_request(f"http://{vm_ip}:{vm_port}{app['url']}"))
        else:
            logger.info(f"Making a request to weblog {weblog_url}")
            request_uuids.append(make_get_request(weblog_url))

        try:
            for request_uuid in request_uuids:
                logger.info(f"Http request done with uuid: [{request_uuid}] for ip [{vm_ip}]")
                wait_backend_trace_id(request_uuid)
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
        vm_logger(context.scenario.host_log_folder, virtual_machine.name).info(
            f"{header} \n {header}  \n  Launching the uninstall for VM: {virtual_machine.name}  \n {header} \n {header}"
        )
        if context.weblog_variant == f"test-app-{context.library.name}":  # Host
            stop_weblog_command = "sudo systemctl kill -s SIGKILL test-app.service"
            start_weblog_command = "sudo systemctl start test-app.service"
            if context.library.name in ["ruby", "python", "dotnet"]:
                start_weblog_command = virtual_machine._vm_provision.weblog_installation.remote_command
        else:  # Container
            stop_weblog_command = "sudo -E docker-compose -f docker-compose.yml down"
            # On older Docker versions, the network recreation can hang. The solution is to restart Docker.
            # https://github.com/docker-archive/classicswarm/issues/1931
            start_weblog_command = "sudo systemctl restart docker && sudo -E docker-compose -f docker-compose.yml up --wait --wait-timeout 120"

        install_command = "sudo datadog-installer apm instrument"
        uninstall_command = "sudo datadog-installer apm uninstrument"
        self._test_uninstall_commands(
            virtual_machine, stop_weblog_command, start_weblog_command, uninstall_command, install_command
        )
