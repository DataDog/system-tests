from collections.abc import Callable
from datetime import datetime
from io import TextIOWrapper
import os
import pathlib
import re
import uuid
import time
import requests
import tempfile
from random import randint
from retry import retry
import json

from pulumi import automation as auto
import pulumi
import pulumi_tls as tls
import pulumi_aws as aws
from pulumi import Output
import pulumi_command as command

from utils._logger import logger
from utils import context
from utils.virtual_machine.vm_logger import vm_logger

from utils.onboarding.debug_vm import download_vm_logs
from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander
from utils.virtual_machine.virtual_machines import _VirtualMachine
from utils.virtual_machine.aws_candidate_boot import CandidateBoot
from utils.virtual_machine.ami_candidate import cache_plan, select_usable_ami, should_boot_created_candidate

import pytest

_VM_LOG_REMOTE_PATHS = ["/var/log/datadog", "/var/log/datadog_weblog", "/tmp/datadog/java"]  # noqa: S108

# Maximum number of concurrent system-tests EC2 instances allowed before waiting for teardown.
_MAX_RUNNING_INSTANCES = 1200
# Datadog event text is truncated to this length before being sent.
_MAX_EVENT_MESSAGE_LENGTH = 255
# Timeout (seconds) for the Datadog event HTTP request.
_EVENT_REQUEST_TIMEOUT = 15
# Short error kept in the pytest exit line. The rest of the Pulumi script stays in the VM log.
_MAX_PROVISION_ERROR_LENGTH = 200
# First Pulumi resource that failed. Later "**creating failed**" lines are cascade noise.
_FAILED_PROVISION_STEP = re.compile(
    r"[\w:]+\s+(?P<name>\S+)\s+\*\*creating failed\*\*"
    r"(?: error: (?P<error>.+?))?(?:: running |\n|$)",
    re.DOTALL,
)


def _provision_step_name(resource_name: str, vm_name: str) -> str | None:
    """Step id from a remote-command resource name, `-{vm}-{step}`. An EC2 instance name is not a step."""
    marker = f"-{vm_name}-"
    index = resource_name.find(marker)
    if index < 0:
        return None
    return resource_name[index + len(marker) :] or None


def _provision_log_hint(vm_name: str, step: str | None) -> str:
    """Where to read the failure: the VM log, and the provision script source."""
    step_hint = f"step '{step}'" if step else "the failed step"
    return (
        f"👀 Check the log file: {vm_name}.log to see the full error trace.\n"
        f"📝 Look for {step_hint} in {vm_name}_provision_script.log to see the source that failed."
    )


def _provision_failure_message(exception_message: str, vm_name: str) -> str:
    """Name the first Pulumi resource that failed, plus a short error."""
    match = _FAILED_PROVISION_STEP.search(exception_message)
    step = _provision_step_name(match.group("name"), vm_name) if match else None
    error = (match.group("error") or "").strip()[:_MAX_PROVISION_ERROR_LENGTH].rstrip() if match else ""
    detail = f" ({error})" if error else ""
    where = f" at step '{step}'" if step else ""
    return f"Error on VM provisioning{where}{detail}.\n{_provision_log_hint(vm_name, step)}"


def _error_diagnostic_line(diagnostic: auto.DiagnosticEvent) -> str | None:
    """One log line for a Pulumi error diagnostic. The remote script after ': running' is dropped."""
    if diagnostic.severity != "error" or diagnostic.ephemeral:
        return None
    message = diagnostic.message.strip()
    marker = ": running "
    running = message.find(marker)
    if running >= 0:
        head = message[:running].strip()
        stderr = message[running + len(marker) :].rsplit("\n", 1)[-1].strip()
        message = head if not stderr or stderr.startswith('"') else f"{head}: {stderr}"
    detail = f"error: {message}"
    # URN shape: urn:pulumi:<stack>::<project>::<type>::<name>
    left, separator, name = diagnostic.urn.rpartition("::") if diagnostic.urn else ("", "", "")
    resource_type = left.rpartition("::")[2]
    if separator and resource_type:
        return f"  {resource_type} ({name}):\n    {detail}"
    return f"  {detail}"


def _select_cached_ami(
    cached_amis: list[aws.ec2.GetAmiResult],
    *,
    now: datetime | None = None,
) -> aws.ec2.GetAmiResult | None:
    return select_usable_ami(cached_amis, now=now)


class AWSPulumiProvider(CandidateBoot, VmProvider):
    def __init__(self):
        super().__init__()
        self.commander = AWSCommander()
        self.pulumi_ssh = None
        self.datadog_event_sender = DatadogEventSender()
        self.stack_name = "system-tests_dev_onboarding"
        self.booted_candidate_ami_id: str | None = None
        self.boot_created_candidate = False
        self.instance_user_data: str | None = None
        self._error_diagnostics: list[str] = []

    def configure(self, virtual_machine: _VirtualMachine) -> None:
        super().configure(virtual_machine)
        # Configure the ssh connection for the VMs
        self.pulumi_ssh = PulumiSSH()
        self.pulumi_ssh.load(virtual_machine)
        self.aws_infra_exceptions = self._load_aws_infra_exceptions()

    def stack_up(self) -> None:
        logger.info(f"Starting AWS VM: {self.vm}")

        def pulumi_start_program() -> None:
            # Static loading of keypairs for ec2 machines
            self.pulumi_ssh = PulumiSSH()
            self.pulumi_ssh.load(self.vm)
            # Debug purposes. How many instances, created by system-tests are running in the AWS account?
            self._check_running_instances()
            # Debug purposes. How many AMI CACHES, created by system-tests are available in the AWS account?
            # self._check_available_cached_amis()
            logger.info("Starting AWS VM.....")
            # First check and configure if there are cached AMIs
            self._configure_cached_amis(self.vm)

            logger.info(
                f"-- Starting AWS VM: [{self.vm.name}], ID:[{self.vm.aws_config.ami_id}], "
                f"update cache:[{self.vm.datadog_config.update_cache}], "
                f"skip cache: [{self.vm.datadog_config.skip_cache}] --"
            )
            self._start_vm(self.vm)

        project_name = "system-tests-vms"
        try:
            self.stack = auto.create_or_select_stack(
                stack_name=self.stack_name, project_name=project_name, program=pulumi_start_program
            )
            if os.getenv("ONBOARDING_LOCAL_TEST") is None:
                self.stack.set_config("aws:SkipMetadataApiCheck", auto.ConfigValue("false"))
            self._stack_up_with_idempotency_retry()
            self.datadog_event_sender.send_event_to_datadog(
                f"[E2E] Stack {self.stack_name}  : success on Pulumi stack up",
                "",
                ["operation:up", "result:ok", f"stack:{self.stack_name}"],
            )
        except pulumi.automation.errors.CommandError as pulumi_command_exception:
            logger.stdout("❌ Exception launching aws provision step remote command ❌")
            vm_logger(context.scenario.host_log_folder, context.vm_name).error(
                "\n \n \n ❌ ❌ ❌ Exception launching aws provision step remote command ❌ ❌ ❌ \n \n \n "
            )
            self._handle_provision_error(pulumi_command_exception)
        except Exception as pulumi_exception:
            logger.stdout("❌ Exception launching aws provision infraestructure ❌ ")
            logger.stdout(
                f"(Please, check the log file: {context.scenario.host_log_folder}/tests.log "
                "and search for the text chain 'Diagnostics:')"
            )
            self._handle_provision_error(pulumi_exception)

    def _stack_up_with_idempotency_retry(self, attempts: int = 3) -> None:
        """Retry the stack up in-process on IdempotentParameterMismatch.

        This is a transient AWS-side token collision (see _start_vm's ec2_resource_id comment).
        A fresh attempt gets a new idempotency token, so it's worth retrying here rather than
        immediately failing the whole CI job (which is a much more expensive way to retry).
        """
        for attempt in range(1, attempts + 1):
            try:
                self._error_diagnostics = []
                self.stack.up(on_output=logger.info, on_event=self._on_pulumi_event)
                return
            except pulumi.automation.errors.CommandError as pulumi_command_exception:
                if "IdempotentParameterMismatch" not in str(pulumi_command_exception) or attempt == attempts:
                    raise
                logger.stdout(f"⚠️ IdempotentParameterMismatch on attempt {attempt}/{attempts}, retrying stack up ⚠️")
                self.stack_destroy()

    def _on_pulumi_event(self, event: auto.EngineEvent) -> None:
        diagnostic = event.diagnostic_event
        if diagnostic is None:
            return
        line = _error_diagnostic_line(diagnostic)
        if line is not None:
            self._error_diagnostics.append(line)

    def get_windows_user_data(self) -> str:
        windows_user_data_path = "utils/build/virtual_machine/provisions/windows_userdata/setup_ssh.ps1"

        # Read the file content as a string
        with open(windows_user_data_path, "r", encoding="utf-8") as file:
            return file.read()

    def _load_aws_infra_exceptions(self):
        """Load the known exceptions for the AWS infraestructure."""
        with open("utils/virtual_machine/aws_infra_exceptions.json", "r") as f:
            return json.load(f)

    def _handle_provision_error(self, exception: BaseException) -> None:
        """Stop the session on any provision error, so that no test is run.

        If the exception is known, exit with code 3 (GitLab retries the job). If not, exit with code 1.
        """

        exception_message = str(exception)
        log = vm_logger(context.scenario.host_log_folder, context.vm_name)
        if self._error_diagnostics:
            match = _FAILED_PROVISION_STEP.search(exception_message)
            step = _provision_step_name(match.group("name"), self.vm.name) if match else None
            title = f"🔧 Diagnostics: {step}" if step else "🔧 Diagnostics:"
            block = title + "\n" + "\n".join(self._error_diagnostics)
            logger.stdout(block)
            log.error(block)
        log.exception(exception)
        for known_id, known_message in self.aws_infra_exceptions.items():
            if known_message in exception_message:
                match = _FAILED_PROVISION_STEP.search(exception_message)
                step = _provision_step_name(match.group("name"), self.vm.name) if match else None
                trace = (
                    f"⚠️ Known infrastructure exception ({known_id}). GitLab will retry this job.\n"
                    f"{known_message}\n"
                    f"{_provision_log_hint(self.vm.name, step)}"
                )
                logger.stdout(trace)
                log.error(trace)
                self.stack_destroy()
                self.datadog_event_sender.send_event_to_datadog(
                    f"[E2E] Stack {self.stack_name} : error on Pulumi stack up. retrying",
                    repr(exception),
                    ["operation:up", "result:retry", f"stack:{self.stack_name}"],
                )
                pytest.exit(f"Known infrastructure exception ({known_id})", returncode=3)
        # If the exception is not known, we will store it in the vm object and error event to dd
        self.vm.provision_install_error = exception
        self._download_vm_logs_after_provision_failure()
        self.datadog_event_sender.send_event_to_datadog(
            f"[E2E] Stack {self.stack_name} : error on Pulumi stack up",
            repr(exception),
            ["operation:up", "result:fail", f"stack:{self.stack_name}"],
        )
        # The stack is destroyed by the scenario's close_targets, called when a warmup fails.
        # Pytest repeats the exit reason, so the log hints are printed once here.
        failure_message = _provision_failure_message(exception_message, self.vm.name)
        logger.stdout(failure_message)
        log.error(failure_message)
        pytest.exit(failure_message.split("\n", 1)[0], returncode=1)

    def _download_vm_logs_after_provision_failure(self) -> None:
        """Pull /var/log from the VM while it is still up (provision may have failed mid-way)."""
        if not self.vm.ssh_config.hostname:
            logger.warning("Cannot download VM logs: VM has no IP yet")
            return
        log_folder = context.scenario.host_log_folder
        logger.stdout(
            f"Downloading VM logs after provision failure into {log_folder} "
            "(including weblog diagnostics and core dumps if present)"
        )
        download_vm_logs(
            vm=self.vm,
            remote_folder_paths=_VM_LOG_REMOTE_PATHS,
            local_base_logs_folder=log_folder,
        )

    def _start_vm(self, vm: _VirtualMachine):
        ec2_user_data = None
        if vm.os_type == "windows":
            if vm.aws_config.ami_id == "AMI_FROM_SSM":
                ssm_parameter = aws.ssm.get_parameter(
                    name="/aws/service/ami-windows-latest/Windows_Server-2022-English-Full-Base"
                )
                logger.info(f"Using Windows AMI: {ssm_parameter.value}")
                vm.aws_config.ami_id = ssm_parameter.value
            ec2_user_data = self.get_windows_user_data()

        self.instance_user_data = ec2_user_data
        self.boot_created_candidate = should_boot_created_candidate(
            update_cache=vm.datadog_config.update_cache,
            skip_cache=vm.datadog_config.skip_cache,
        )
        ec2_server, server_connection = self._launch_instance(
            vm,
            vm.aws_config.ami_id,
            None,
            ec2_user_data,
            publish_ip=True,
            name_suffix="",
            export_suffix="_builder" if self.boot_created_candidate else "",
        )
        self.install_provision(vm, ec2_server, server_connection)

    def stack_destroy(self) -> None:
        if os.getenv("ONBOARDING_KEEP_VMS") is None:
            logger.info(f"Destroying VM: {self.vm}")
            try:
                self.stack.destroy(on_output=logger.info, debug=True)
                self.datadog_event_sender.send_event_to_datadog(
                    f"[E2E] Stack {self.stack_name}  : success on Pulumi stack destroy",
                    "",
                    ["operation:destroy", "result:ok", f"stack:{self.stack_name}"],
                )
            except Exception as pulumi_exception:
                logger.error("Exception destroying aws provision infraestructure")
                logger.exception(pulumi_exception)
                self.datadog_event_sender.send_event_to_datadog(
                    f"[E2E] Stack {self.stack_name}  : error on Pulumi stack destroy",
                    repr(pulumi_exception),
                    ["operation:destroy", "result:fail", f"stack:{self.stack_name}"],
                )
        else:
            logger.info(
                "Did not destroy VM as ONBOARDING_KEEP_VMS is set. "
                "To destroy them, re-run the test without this env var."
            )

    def _get_cached_amis(self, vm: _VirtualMachine) -> list[aws.ec2.GetAmiResult]:
        """Get all the cached AMIs for the VM"""
        ami_ids = aws.ec2.get_ami_ids(
            filters=[aws.ec2.GetAmiIdsFilterArgs(name="name", values=[vm.get_cache_name() + "-*"])],
            owners=["self"],
        ).ids
        cached_amis = [
            aws.ec2.get_ami(
                filters=[aws.ec2.GetAmiIdsFilterArgs(name="image-id", values=[ami_id])],
                owners=["self"],
                most_recent=True,
            )
            for ami_id in ami_ids
        ]
        for cached_ami in cached_amis:
            logger.stdout(
                f"We found an existing AMI  name:[{cached_ami.name}], ID:[{cached_ami.id}], "
                f"status:[{cached_ami.state}], expiration:[{cached_ami.deprecation_time}], "
                f"created:[{cached_ami.creation_date}]"
            )
        return cached_amis

    def _configure_cached_amis(self, vm: _VirtualMachine) -> None:
        """Configure the cached AMIs for the VM"""
        # We don't want to use cache ami for skip_ami_cache or ami_update
        if vm.datadog_config.skip_cache or vm.datadog_config.update_cache:
            return

        before_time = time.time()
        cached_ami = _select_cached_ami(self._get_cached_amis(vm))
        plan = cache_plan(cached_ami)
        if plan == "create":
            vm.datadog_config.update_cache = True
        elif plan == "wait" and cached_ami is not None:
            logger.stdout(
                f"Cache AMI [{cached_ami.id}] for [{vm.name}] is not ready "
                f"(status={cached_ami.state}, ami-state={(cached_ami.tags or {}).get('ami-state')}). "
                "This job will not create another AMI."
            )
            vm.datadog_config.update_cache = False
            vm.datadog_config.skip_cache = True
        else:
            logger.stdout(
                f"Setting cached AMI for VM [{vm.name}] from base AMI ID [{vm.aws_config.ami_id}] "
                f"to cached AMI ID [{cached_ami.id}]"
            )
            vm.aws_config.ami_id = cached_ami.id

        logger.info(f"Time cache for AMIs: {time.time() - before_time}")

    def _get_ec2_tags(self, vm: _VirtualMachine):
        """Build the ec2 tags for the VM"""
        tags = {"Name": vm.name, "CI": "system-tests"}

        if os.getenv("CI_PROJECT_NAME") is not None:
            tags["CI_PROJECT_NAME"] = os.getenv("CI_PROJECT_NAME")

        if os.getenv("CI_PIPELINE_ID") is not None:
            tags["CI_PIPELINE_ID"] = os.getenv("CI_PIPELINE_ID")

        if os.getenv("CI_JOB_ID") is not None:
            tags["CI_JOB_ID"] = os.getenv("CI_JOB_ID")
        logger.info(f"Tags for the VM [{vm.name}]: {tags}")
        return tags

    @retry(delay=10, tries=30)
    def _check_running_instances(self):
        """Check the number of running instances in the AWS account
        if there are more than 500 instances, we will wait until they are destroyed
        """

        ec2_ids = self._print_running_instances()
        if len(ec2_ids) > _MAX_RUNNING_INSTANCES:
            logger.stdout("THERE ARE TOO MANY EC2 INSTANCES RUNNING. Waiting for the instances to be destroyed")
            raise RuntimeError("Too many ec2 instances running")

    def _print_running_instances(self):
        """Print the instances created by system-tests and still running in the AWS account"""

        instances = aws.ec2.get_instances(instance_tags={"CI": "system-tests"}, instance_state_names=["running"])

        logger.info("AWS Listing running instances with system-tests tag")
        for instance_id in instances.ids:
            logger.info(f"- Instance id: [{instance_id}]  status:[running] (created by other execution)")

        logger.info(f"Total tags: {instances.instance_tags}")
        return instances.ids

    def _check_available_cached_amis(self):
        """Print the AMI Caches availables in the AWS account and created by system-tests"""
        try:
            logger.info("AWS Listing available ami caches with system-tests tag")
            ami_existing = aws.ec2.get_ami_ids(
                filters=[aws.ec2.GetAmiIdsFilterArgs(name="tag:CI", values=["system-tests"])], owners=["self"]
            )
            for ami in ami_existing.ids:
                # Latest ami details
                ami_recent = aws.ec2.get_ami(
                    filters=[aws.ec2.GetAmiIdsFilterArgs(name="image-id", values=[ami])],
                    owners=["self"],
                    most_recent=True,
                )
                logger.info(
                    f"* name:[{ami_recent.name}], ID:[{ami_recent.id}], status:[{ami_recent.state}], "
                    f"expiration:[{ami_recent.deprecation_time}], created:[{ami_recent.creation_date}]"
                )
        except Exception as e:
            logger.error(f"Error checking cached AMIs: {e}")
            logger.info("No cached AMIs found in the account")


class AWSCommander(Commander):
    def create_cache(
        self, vm: _VirtualMachine, server: aws.ec2.Instance, last_task: command.remote.Command
    ) -> aws.ec2.AmiFromInstance:
        """Create an AMI cache from the current server state."""
        ami_name = vm.get_cache_name()
        logger.stdout(f"Creating AMI with name [{ami_name}] from instance ")
        vm_logger(context.scenario.host_log_folder, "cache_created").info(f"[{context.scenario.name}] - [{ami_name}]")

        return aws.ec2.AmiFromInstance(
            ami_name,
            description=ami_name,
            source_instance_id=server.id,
            opts=pulumi.ResourceOptions(depends_on=[last_task], retain_on_delete=True),
            tags={"CI": "system-tests", "ami-cache-key": ami_name, "ami-state": "candidate"},
        )

    def execute_local_command(
        self,
        local_command_id: str,
        local_command: str,
        env: dict[str, str],
        last_task: command.remote.Command,
        logger_name: str,
    ) -> command.local.Command:
        local_task = command.local.Command(
            local_command_id,
            create=local_command,
            opts=pulumi.ResourceOptions(depends_on=[last_task]),
            environment=env,
        )
        local_task.stdout.apply(
            lambda outputlog: vm_logger(context.scenario.host_log_folder, logger_name).info(outputlog)
        )
        return local_task

    def copy_file(
        self,
        copy_id: str,
        local_path: str,
        remote_path: str,
        connection: command.remote.ConnectionArgs,
        last_task: command.remote.Command,
        vm: _VirtualMachine | None = None,  # noqa: ARG002
    ) -> command.remote.CopyFile:
        return command.remote.CopyFile(
            copy_id,
            connection=connection,
            local_path=local_path,
            remote_path=remote_path,
            opts=pulumi.ResourceOptions(depends_on=[last_task], retain_on_delete=True),
        )

    def remote_command(
        self,
        vm: _VirtualMachine,
        installation_id: str,
        remote_command: str,
        env: dict[str, str],
        connection: command.remote.ConnectionArgs,
        last_task: command.remote.Command,
        logger_name: str | None = None,
        output_callback: Callable | None = None,
        *,
        populate_env: bool = True,
    ) -> command.remote.Command:
        if not populate_env:
            ##error: Unable to set 'DD_env'. This only works if your SSH server is configured to accept
            logger.debug(f"No populate environment variables for installation id: {installation_id} ")
            env = {}

        cmd_exec_install = command.remote.Command(
            f"-{vm.name}-{installation_id}",
            connection=connection,
            create=remote_command,
            environment=env,
            opts=pulumi.ResourceOptions(depends_on=[last_task], retain_on_delete=True),
        )
        if logger_name:
            cmd_exec_install.stdout.apply(
                lambda outputlog: vm_logger(context.scenario.host_log_folder, logger_name).info(outputlog)
            )
        else:
            # No logger name specified: group all logs of the same remote machine by host/ip name.
            header = "\n *****************************************************************"
            header2 = "\n -----------------------------------------------------------------"

            def _log_remote_command_output(args: list[object]) -> None:
                vm_name = str(args[0])
                step_id = str(args[1])
                command = str(args[2])
                stdout = str(args[3] or "")
                stderr = str(args[4] or "")
                failed = "Process exited with status" in stderr or "error:" in stderr.lower()
                status = "❌ FAILED" if failed else "✅ SUCCESS"
                vm_logger(context.scenario.host_log_folder, vm_name).info(
                    f"{header} \n   🚀 Provision step: {step_id} 🚀 \n      Status: {status} \n {header} \n"
                    f" {command} \n\n {header2} \n 📤 Provision step output ({step_id}) 📤  \n {header2} \n"
                    f" {stdout} \n\n {header2} \n 🚨 error output ({step_id}) 🚨 \n {header2} \n {stderr}"
                )

            Output.all(
                vm.name, installation_id, remote_command, cmd_exec_install.stdout, cmd_exec_install.stderr
            ).apply(_log_remote_command_output)
        if output_callback:
            Output.all(vm, cmd_exec_install.stdout).apply(output_callback)

        return cmd_exec_install

    def remote_copy_folders(
        self,
        source_folder: str,
        destination_folder: str | None,
        command_id: str,
        connection: command.remote.ConnectionArgs,
        depends_on: command.remote.Command,
        *,
        relative_path: bool = False,
        vm: _VirtualMachine | None = None,
    ) -> command.remote.Command:
        # If we don't use remote_path, the remote_path will be a default remote user home
        if not destination_folder:
            destination_folder = pathlib.Path(source_folder).name

        quee_depends_on = [depends_on]
        for file_name in (entry.name for entry in pathlib.Path(source_folder).iterdir()):
            # construct full file path
            source = source_folder + "/" + file_name
            destination = destination_folder + "/" + file_name
            # logger.debug(f"remote_copy_folders: source:[{source}] and remote destination: [{destination}] ")

            if pathlib.Path(source).is_file():
                if not relative_path:
                    destination = pathlib.Path(destination).name

                # logger.debug(f"Copy single file: source:[{source}] and remote destination: [{destination}] ")
                # Launch copy file command
                quee_depends_on.insert(
                    0,
                    command.remote.CopyFile(
                        source + "-" + command_id,
                        connection=connection,
                        local_path=source,
                        remote_path=destination,
                        opts=pulumi.ResourceOptions(depends_on=[quee_depends_on.pop()], retain_on_delete=True),
                    ),
                )
            else:
                # mkdir remote
                if not relative_path:
                    p = pathlib.Path("/" + destination)
                    destination = str(p.relative_to(*p.parts[:2]))
                # logger.debug(f"Creating remote folder: {destination}")

                # Use different mkdir commands based on OS type
                mkdir_cmd = (
                    "mkdir -p" if not vm or vm.os_type != "windows" else "New-Item -ItemType Directory -Force -Path"
                )
                quee_depends_on.insert(
                    0,
                    command.remote.Command(
                        "mkdir-" + destination + "-" + str(uuid.uuid4()) + "-" + command_id,
                        connection=connection,
                        create=f"{mkdir_cmd} {destination}",
                        opts=pulumi.ResourceOptions(depends_on=[quee_depends_on.pop()], retain_on_delete=True),
                    ),
                )
                quee_depends_on.insert(
                    0,
                    self.remote_copy_folders(
                        source, destination, command_id, connection, quee_depends_on.pop(), relative_path=True, vm=vm
                    ),
                )
        return quee_depends_on.pop()  # Here the quee should contain only one element


class PulumiSSH:
    keypair_name = None
    private_key_pem = None
    aws_key_resource = None
    pem_file = None

    def load(self, virtual_machine: _VirtualMachine) -> None:
        # Optional parameters. You can use for local testing
        user_provided_key_pair_name = os.getenv("ONBOARDING_AWS_INFRA_KEYPAIR_NAME")
        user_provided_private_key_path = os.getenv("ONBOARDING_AWS_INFRA_KEY_PATH")
        # SSH Keys: Two options. 1. Use your own keypair and pem file. 2.
        # Create a new one and automatically destroy after the test
        if user_provided_key_pair_name and user_provided_private_key_path:
            logger.info("Using a existing key pair")
            self.keypair_name = user_provided_key_pair_name
            self.pem_file = user_provided_private_key_path
            with open(user_provided_private_key_path, encoding="utf-8") as f:
                self.private_key_pem = f.read()
            virtual_machine.ssh_config.pkey_path = user_provided_private_key_path
        else:
            logger.info("Creating new ssh key")
            key_name = "onboarding_test_key_name" + str(randint(0, 1000000))
            ssh_key = tls.PrivateKey(key_name, algorithm="RSA", rsa_bits=4096)
            self.private_key_pem = ssh_key.private_key_pem
            aws_key = aws.ec2.KeyPair(
                key_name,
                key_name=key_name,
                public_key=ssh_key.public_key_openssh,
                opts=pulumi.ResourceOptions(parent=ssh_key),
            )
            self.keypair_name = aws_key.key_name
            self.aws_key_resource = pulumi.ResourceOptions(depends_on=[aws_key])

            # Create temporary file to use the pem file in other ssh connections (outside of Pulumi context)
            logger.info("Creating temporary pem file")
            _, pem_file_path = tempfile.mkstemp()
            # File is intentionally kept open: it is written later by a Pulumi Output callback.
            pem_file = open(pem_file_path, "w", encoding="utf-8")  # noqa: SIM115  # pylint: disable=R1732
            ssh_key.private_key_pem.apply(lambda out: self._write_pem_file(pem_file, out))
            virtual_machine.ssh_config.pkey_path = pem_file_path

        virtual_machine.ssh_config.username = virtual_machine.aws_config.user

    def _write_pem_file(self, pem_file: TextIOWrapper, content: str):
        pem_file.write(content)
        pem_file.close()


class DatadogEventSender:
    """Send events to Datadog ddev organization"""

    def __init__(self):
        self.ddev_api_key: str = os.getenv("DDEV_API_KEY")
        self.ci_project_name: str = os.getenv("CI_PROJECT_NAME", "local")
        self.ci_job_url: str = os.getenv("CI_JOB_URL", "local")

    def send_event_to_datadog(self, title: str, message: str, tags: list[str]) -> None:
        if not self.ddev_api_key:
            logger.error("Datadog API key not found to send event to ddev organization. Skipping event.")
            return
        logger.debug("Sending event to datadog ddev organization")
        try:
            host = "https://dddev.datadoghq.com/api/v1/events"
            headers = {"DD-API-KEY": self.ddev_api_key}

            default_tags = [
                "repository:system-tests",
                f"job_url:{self.ci_job_url}",
                f"scenario:{context.scenario.name}",
                f"library:{context.library.name}",
                f"weblog:{context.weblog_variant}",
                "source:pulumi",
            ]
            default_tags = default_tags + tags
            default_tags.append(f"ci_project_name:{self.ci_project_name}")
            data_to_send = {
                "title": title,
                "text": (message[:_MAX_EVENT_MESSAGE_LENGTH] + "..")
                if len(message) > _MAX_EVENT_MESSAGE_LENGTH
                else message,
                "tags": default_tags,
            }
            logger.debug(f"Sending event payload: [{data_to_send}]")
            r = requests.post(host, headers=headers, json=data_to_send, timeout=_EVENT_REQUEST_TIMEOUT)
            logger.debug(f"Backend response status for sending event: [{r.status_code}]")

        except Exception as e:
            logger.error(f"Error sending events to datadog ddevn organization {e} ")
