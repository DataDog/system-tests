import os
import pathlib
import uuid
import time
import requests
import tempfile
from random import randint
from retry import retry
import json
import random

from pulumi import automation as auto
import pulumi
import pulumi_tls as tls
import pulumi_aws as aws
from pulumi import Output
import pulumi_command as command

from utils._logger import logger
from utils import context
from utils.virtual_machine.vm_logger import vm_logger

from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander


class AWSPulumiProvider(VmProvider):
    def __init__(self):
        super().__init__()
        self.commander = AWSCommander()
        self.pulumi_ssh = None
        self.datadog_event_sender = DatadogEventSender()
        self.stack_name = "system-tests_onboarding"

    def configure(self, virtual_machine):
        super().configure(virtual_machine)
        # Configure the ssh connection for the VMs
        self.pulumi_ssh = PulumiSSH()
        self.pulumi_ssh.load(virtual_machine)
        self.aws_infra_exceptions = self._load_aws_infra_exceptions()

    def stack_up(self):
        logger.info(f"Starting AWS VM: {self.vm}")

        def pulumi_start_program():
            # Static loading of keypairs for ec2 machines
            self.pulumi_ssh = PulumiSSH()
            self.pulumi_ssh.load(self.vm)
            # Debug purposes. How many instances, created by system-tests are running in the AWS account?
            self._check_running_instances()
            # Debug purposes. How many AMI CACHES, created by system-tests are available in the AWS account?
            # self._check_available_cached_amis()
            logger.info(f"Starting AWS VM.....")
            # First check and configure if there are cached AMIs
            self._configure_cached_amis(self.vm)

            logger.info(
                f"-- Starting AWS VM: [{self.vm.name}], ID:[{self.vm.aws_config.ami_id}], update cache:[{self.vm.datadog_config.update_cache}], skip cache: [{ self.vm.datadog_config.skip_cache}] --"
            )
            self._start_vm(self.vm)

        project_name = "system-tests-vms"
        try:
            self.stack = auto.create_or_select_stack(
                stack_name=self.stack_name, project_name=project_name, program=pulumi_start_program
            )
            if os.getenv("ONBOARDING_LOCAL_TEST") is None:
                self.stack.set_config("aws:SkipMetadataApiCheck", auto.ConfigValue("false"))
            up_res = self.stack.up(on_output=logger.info)
            self.datadog_event_sender.sendEventToDatadog(
                f"[E2E] Stack {self.stack_name}  : success on Pulumi stack up",
                "",
                ["operation:up", "result:ok", f"stack:{self.stack_name}"],
            )
        except pulumi.automation.errors.CommandError as pulumi_command_exception:
            logger.stdout("❌ Exception launching aws provision step remote command ❌")
            logger.stdout(f"(Please, check the log file: {context.vm_name}.log)")
            vm_logger(context.scenario.host_log_folder, context.vm_name).error(
                "\n \n \n ❌ ❌ ❌ Exception launching aws provision step remote command ❌ ❌ ❌ \n \n \n "
            )
            vm_logger(context.scenario.host_log_folder, context.vm_name).exception(pulumi_command_exception)
            self._handle_provision_error(pulumi_command_exception)
        except Exception as pulumi_exception:
            logger.stdout("❌ Exception launching aws provision infraestructure ❌ ")
            logger.stdout(f"(Please, check the log file: tests.log and search for the text chain 'Diagnostics:')")
            logger.debug(f"The error class name: { pulumi_exception.__class__.__name__}")
            self._handle_provision_error(pulumi_exception)

    def get_windows_user_data(self):
        windows_user_data_path = "utils/build/virtual_machine/provisions/windows_userdata/setup_ssh.ps1"

        # Read the file content as a string
        with open(windows_user_data_path, "r", encoding="utf-8") as file:
            windows_user_data_content = file.read()

        return windows_user_data_content

    def _load_aws_infra_exceptions(self):
        """Load the known exceptions for the AWS infraestructure."""
        with open("utils/virtual_machine/aws_infra_exceptions.json", "r") as f:
            return json.load(f)

    def _handle_provision_error(self, exception):
        """If the exception is known, we will raise the exception, if not,we will store it in the vm object."""

        exception_message = str(exception)
        for known_message in self.aws_infra_exceptions.values():
            if known_message in exception_message:
                self.stack_destroy()
                self.datadog_event_sender.sendEventToDatadog(
                    f"[E2E] Stack {self.stack_name} : error on Pulumi stack up. retrying",
                    repr(exception),
                    ["operation:up", "result:retry", f"stack:{self.stack_name}"],
                )
                raise exception  # Re-raise the exception if matched
        # If the exception is not known, we will store it in the vm object and error event to dd
        self.vm.provision_install_error = exception
        self.datadog_event_sender.sendEventToDatadog(
            f"[E2E] Stack {self.stack_name} : error on Pulumi stack up",
            repr(exception),
            ["operation:up", "result:fail", f"stack:{self.stack_name}"],
        )

    def _start_vm(self, vm):
        ec2_user_data = None
        if vm.os_type == "windows":
            if vm.aws_config.ami_id == "AMI_FROM_SSM":
                ssm_parameter = aws.ssm.get_parameter(
                    name="/aws/service/ami-windows-latest/Windows_Server-2022-English-Full-Base"
                )
                logger.info(f"Using Windows AMI: {ssm_parameter.value}")
                vm.aws_config.ami_id = ssm_parameter.value
            ec2_user_data = self.get_windows_user_data()

        logger.info(
            f"Starting VM: {vm.name} with iam_instance_profile: {vm.aws_config.aws_infra_config.iam_instance_profile}"
        )
        # Startup VM and prepare connection
        ec2_server = aws.ec2.Instance(
            vm.name,
            instance_type=vm.aws_config.ami_instance_type,
            vpc_security_group_ids=vm.aws_config.aws_infra_config.vpc_security_group_ids,
            subnet_id=random.choice(vm.aws_config.aws_infra_config.subnet_id),
            key_name=self.pulumi_ssh.keypair_name,
            ami=vm.aws_config.ami_id,
            tags=self._get_ec2_tags(vm),
            opts=self.pulumi_ssh.aws_key_resource,
            root_block_device={"volume_size": vm.aws_config.volume_size},
            iam_instance_profile=vm.aws_config.aws_infra_config.iam_instance_profile,
            user_data=ec2_user_data,
        )
        # Store the private ip of the vm: store it in the vm object and export it. Log to vm_desc.log
        Output.all(vm, ec2_server.private_ip).apply(lambda args: args[0].set_ip(args[1]))
        pulumi.export("privateIp_" + vm.name, ec2_server.private_ip)
        Output.all(ec2_server.private_ip, vm.name, ec2_server.id).apply(
            lambda args: vm_logger(context.scenario.host_log_folder, "vms_desc").info(f"{args[0]}:{args[1]}:{args[2]}")
        )

        vm.ssh_config.username = vm.aws_config.user

        server_connection = command.remote.ConnectionArgs(
            host=ec2_server.private_ip,
            user=vm.aws_config.user,
            private_key=self.pulumi_ssh.private_key_pem,
            # dial_error_limit=30 retries, 10 seconds per retry=5 minutes.
            # WARNING:: If you change that, please change  the key 'error_ssh_connection' in aws_infra_exceptions.json
            dial_error_limit=30,
            per_dial_timeout=10,
        )
        # Install provision on the started server
        self.install_provision(vm, ec2_server, server_connection)

    def stack_destroy(self):
        if os.getenv("ONBOARDING_KEEP_VMS") is None:
            logger.info(f"Destroying VM: {self.vm}")
            try:
                self.stack.destroy(on_output=logger.info, debug=True)
                self.datadog_event_sender.sendEventToDatadog(
                    f"[E2E] Stack {self.stack_name}  : success on Pulumi stack destroy",
                    "",
                    ["operation:destroy", "result:ok", f"stack:{self.stack_name}"],
                )
            except Exception as pulumi_exception:
                logger.error("Exception destroying aws provision infraestructure")
                logger.exception(pulumi_exception)
                self.datadog_event_sender.sendEventToDatadog(
                    f"[E2E] Stack {self.stack_name}  : error on Pulumi stack destroy",
                    repr(pulumi_exception),
                    ["operation:destroy", "result:fail", f"stack:{self.stack_name}"],
                )
        else:
            logger.info(
                f"Did not destroy VM as ONBOARDING_KEEP_VMS is set. To destroy them, re-run the test without this env var."
            )

    def _get_cached_amis(self, vm):
        """Get all the cached AMIs for the VM"""
        names_filter_to_check = []
        cached_amis = []
        # Create search filter if vm is not marked as skip_cache or update_cache

        if not vm.datadog_config.skip_cache and not vm.datadog_config.update_cache:
            names_filter_to_check.append(vm.get_cache_name() + "-*")

        # There are vms that should use the cache
        if len(names_filter_to_check) > 0:
            # Check for existing ami cache for the vm
            ami_existing = aws.ec2.get_ami_ids(
                filters=[aws.ec2.GetAmiIdsFilterArgs(name="name", values=names_filter_to_check)], owners=["self"]
            )
            # We found some cached AMIsm let's check the details: status, expiration, etc
            for ami in ami_existing.ids:
                # Latest ami details
                ami_recent = aws.ec2.get_ami(
                    filters=[aws.ec2.GetAmiIdsFilterArgs(name="image-id", values=[ami])],
                    owners=["self"],
                    most_recent=True,
                )
                logger.stdout(
                    f"We found an existing AMI  name:[{ami_recent.name}], ID:[{ami_recent.id}], status:[{ami_recent.state}], expiration:[{ami_recent.deprecation_time}], created:[{ami_recent.creation_date}]"
                )
                cached_amis.append(ami_recent)
        return cached_amis

    def _configure_cached_amis(self, vm):
        """Configure the cached AMIs for the VM"""
        before_time = time.time()
        cached_amis = self._get_cached_amis(vm)
        # We don't want to use cache ami for skip_ami_cache or ami_update
        if vm.datadog_config.skip_cache or vm.datadog_config.update_cache:
            return
        # Let's search the cached AMI for the VM
        cached_ami_found = False
        for cached_ami in cached_amis:
            # The final name it's the vm.get_cache_name() + "-somethingaddedbyaws"
            if vm.name in cached_ami.name:
                if str(cached_ami.state) != "available":
                    logger.stdout(
                        f"We found an existing cache AMI for vm [{vm.name}] but we can no use it because the current status is {cached_ami.state}"
                    )
                    logger.stdout(
                        "We are not going to create a new AMI and we are not going to use it (skip cache mode)"
                    )
                    vm.datadog_config.update_cache = False
                    vm.datadog_config.skip_cache = True
                else:
                    logger.stdout(
                        f"Setting cached AMI for VM [{vm.name}] from base AMI ID [{vm.aws_config.ami_id}] to cached AMI ID [{cached_ami.id}]"
                    )
                    vm.aws_config.ami_id = cached_ami.id
                cached_ami_found = True
                break

        # Here we don't find a cached AMI for the VM. Force creation
        if not cached_ami_found:
            vm.datadog_config.update_cache = True

        logger.info(f"Time cache for AMIs: {time.time() - before_time}")

    def _get_ec2_tags(self, vm):
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
        if len(ec2_ids) > 700:
            logger.stdout(f"THERE ARE TOO MANY EC2 INSTANCES RUNNING. Waiting for the instances to be destroyed")
            raise Exception("Too many ec2 instances running")

    def _print_running_instances(self):
        """Print the instances created by system-tests and still running in the AWS account"""

        instances = aws.ec2.get_instances(instance_tags={"CI": "system-tests"}, instance_state_names=["running"])

        logger.info(f"AWS Listing running instances with system-tests tag")
        for instance_id in instances.ids:
            logger.info(f"- Instance id: [{instance_id}]  status:[running] (created by other execution)")

        logger.info(f"Total tags: {instances.instance_tags}")
        return instances.ids

    def _check_available_cached_amis(self):
        """Print the AMI Caches availables in the AWS account and created by system-tests"""
        try:
            logger.info(f"AWS Listing available ami caches with system-tests tag")
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
                    f"* name:[{ami_recent.name}], ID:[{ami_recent.id}], status:[{ami_recent.state}], expiration:[{ami_recent.deprecation_time}], created:[{ami_recent.creation_date}]"
                )
        except Exception as e:
            logger.error(f"Error checking cached AMIs: {e}")
            logger.info("No cached AMIs found in the account")


class AWSCommander(Commander):
    def create_cache(self, vm, server, last_task):
        """Create a cache : Create an AMI from the server current status."""
        ami_name = vm.get_cache_name()
        # Ok. All third party software is installed, let's create the ami to reuse it in the future
        logger.stdout(f"Creating AMI with name [{ami_name}] from instance ")
        vm_logger(context.scenario.host_log_folder, "cache_created").info(f"[{context.scenario.name}] - [{ami_name}]")

        # Expiration date for the ami
        # expiration_date = (datetime.now() + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task_dep = aws.ec2.AmiFromInstance(
            ami_name,
            description=ami_name,
            # deprecation_time=expiration_date,
            source_instance_id=server.id,
            opts=pulumi.ResourceOptions(depends_on=[last_task], retain_on_delete=True),
            tags={"CI": "system-tests"},
        )
        return task_dep

    def execute_local_command(self, local_command_id, local_command, env, last_task, logger_name):
        last_task = command.local.Command(
            local_command_id,
            create=local_command,
            opts=pulumi.ResourceOptions(depends_on=[last_task]),
            environment=env,
        )
        last_task.stdout.apply(
            lambda outputlog: vm_logger(context.scenario.host_log_folder, logger_name).info(outputlog)
        )
        return last_task

    def copy_file(self, id, local_path, remote_path, connection, last_task, vm=None):
        last_task = command.remote.CopyFile(
            id,
            connection=connection,
            local_path=local_path,
            remote_path=remote_path,
            opts=pulumi.ResourceOptions(depends_on=[last_task], retain_on_delete=True),
        )
        return last_task

    def remote_command(
        self,
        vm,
        installation_id,
        remote_command,
        env,
        connection,
        last_task,
        logger_name=None,
        output_callback=None,
        populate_env=True,
    ):
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
            # If there isn't logger name specified, we will use the host/ip name to store all the logs of the
            # same remote machine in the same log file
            # If there is a failure (exit != 0) this trace will not be stored in the log file (why?)
            header = "\n *****************************************************************"
            header2 = "\n -----------------------------------------------------------------"
            Output.all(
                vm.name, installation_id, remote_command, cmd_exec_install.stdout, cmd_exec_install.stderr
            ).apply(
                lambda args: vm_logger(context.scenario.host_log_folder, args[0]).info(
                    f"{header} \n   🚀 Provision step: {args[1]} 🚀 \n      Status: ✅ SUCCESS \n {header} \n {args[2]} \n\n {header2} \n 📤 Provision step output ({args[1]}) 📤  \n {header2} \n {args[3]} \n\n {header2} \n 🚨 error output ({args[1]}) 🚨 \n {header2} \n {args[4]}"
                )
            )
        if output_callback:
            Output.all(vm, cmd_exec_install.stdout).apply(output_callback)

        return cmd_exec_install

    def remote_copy_folders(
        self, source_folder, destination_folder, command_id, connection, depends_on, relative_path=False, vm=None
    ):
        # If we don't use remote_path, the remote_path will be a default remote user home
        if not destination_folder:
            destination_folder = os.path.basename(source_folder)

        quee_depends_on = [depends_on]
        for file_name in os.listdir(source_folder):
            # construct full file path
            source = source_folder + "/" + file_name
            destination = destination_folder + "/" + file_name
            # logger.debug(f"remote_copy_folders: source:[{source}] and remote destination: [{destination}] ")

            if os.path.isfile(source):
                if not relative_path:
                    destination = os.path.basename(destination)

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

    def load(self, virtual_machine):
        # Optional parameters. You can use for local testing
        user_provided_keyPairName = os.getenv("ONBOARDING_AWS_INFRA_KEYPAIR_NAME")
        user_provided_privateKeyPath = os.getenv("ONBOARDING_AWS_INFRA_KEY_PATH")
        # SSH Keys: Two options. 1. Use your own keypair and pem file. 2.
        # Create a new one and automatically destroy after the test
        if user_provided_keyPairName and user_provided_privateKeyPath:
            logger.info("Using a existing key pair")
            self.keypair_name = user_provided_keyPairName
            self.pem_file = user_provided_privateKeyPath
            with open(user_provided_privateKeyPath, encoding="utf-8") as f:
                self.private_key_pem = f.read()
            virtual_machine.ssh_config.pkey_path = user_provided_privateKeyPath
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
            pem_file = open(pem_file_path, "w", encoding="utf-8")  # pylint: disable=R1732
            ssh_key.private_key_pem.apply(lambda out: self._write_pem_file(pem_file, out))
            virtual_machine.ssh_config.pkey_path = pem_file_path

        virtual_machine.ssh_config.username = virtual_machine.aws_config.user

    def _write_pem_file(self, pem_file, content):
        pem_file.write(content)
        pem_file.close()


class DatadogEventSender:
    """Send events to Datadog ddev organization"""

    def __init__(self):
        self.ddev_api_key = os.getenv("DDEV_API_KEY")
        self.ci_project_name = os.getenv("CI_PROJECT_NAME", "local")
        self.ci_job_url = os.getenv("CI_JOB_URL", "local")

    def sendEventToDatadog(self, title, message, tags):
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
                "text": (message[:255] + "..") if len(message) > 255 else message,
                "tags": default_tags,
            }
            logger.debug(f"Sending event payload: [{data_to_send}]")
            r = requests.post(host, headers=headers, json=data_to_send)
            logger.debug(f"Backend response status for sending event: [{r.status_code}]")

        except Exception as e:
            logger.error(f"Error sending events to datadog ddevn organization {e} ")
