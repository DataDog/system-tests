import os
import pathlib
import uuid
import paramiko

from pulumi import automation as auto
import pulumi
import pulumi_aws as aws
from pulumi import Output
import pulumi_command as command

from utils.tools import logger
from utils import context
from utils.onboarding.pulumi_ssh import PulumiSSH
from utils.onboarding.pulumi_utils import pulumi_logger
from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander


class AWSPulumiProvider(VmProvider):
    def __init__(self):
        super().__init__()
        self.commander = AWSCommander()

    def stack_up(self):
        logger.info(f"Starting AWS VMs: {self.vms}")

        def pulumi_start_program():
            # Static loading of keypairs for ec2 machines
            PulumiSSH.load()
            for vm in self.vms:
                logger.info(f"--------- Starting AWS VM: {vm.name} -----------")
                self._start_vm(vm)

        project_name = "system-tests-vms"
        stack_name = "testing_v3"

        try:
            self.stack = auto.create_or_select_stack(
                stack_name=stack_name, project_name=project_name, program=pulumi_start_program
            )
            self.stack.set_config("aws:SkipMetadataApiCheck", auto.ConfigValue("false"))
            up_res = self.stack.up(on_output=logger.info)
        except Exception as pulumi_exception:  #
            logger.error("Exception launching aws provision infraestructure")
            logger.exception(pulumi_exception)

    def _start_vm(self, vm):
        # Check for cached ami, before starting a new one
        ami_id = self._get_cached_ami(vm)
        logger.info(f"Cache AMI: {vm.get_cache_name()}")

        # Startup VM and prepare connection
        ec2_server = aws.ec2.Instance(
            vm.name,
            instance_type=vm.aws_config.ami_instance_type,
            vpc_security_group_ids=vm.aws_config.aws_infra_config.vpc_security_group_ids,
            subnet_id=vm.aws_config.aws_infra_config.subnet_id,
            key_name=PulumiSSH.keypair_name,
            ami=vm.aws_config.ami_id if ami_id is None else ami_id,
            tags={"Name": vm.name,},
            opts=PulumiSSH.aws_key_resource,
        )

        # Store the private ip of the vm: store it in the vm object and export it. Log to vm_desc.log
        Output.all(vm, ec2_server.private_ip).apply(lambda args: args[0].set_ip(args[1]))
        pulumi.export("privateIp_" + vm.name, ec2_server.private_ip)
        Output.all(ec2_server.private_ip, vm.name).apply(
            lambda args: pulumi_logger(context.scenario.name, "vms_desc").info(f"{args[0]}:{args[1]}")
        )
        # Configure ssh connection
        # Output.all(ec2_server.private_ip, vm).apply(
        #    vm.ssh_config.set_pkey(paramiko.RSAKey.from_private_key_file(PulumiSSH.pem_file))
        # )
        vm.ssh_config.username = vm.aws_config.user

        server_connection = command.remote.ConnectionArgs(
            host=ec2_server.private_ip,
            user=vm.aws_config.user,
            private_key=PulumiSSH.private_key_pem,
            dial_error_limit=-1,
        )
        # Install provision on the started server
        self.install_provision(vm, ec2_server, server_connection, create_cache=ami_id is None)

    def stack_destroy(self):
        logger.info(f"Destroying VMs: {self.vms}")
        self.stack.destroy(on_output=logger.info)

    def _get_cached_ami(self, vm):
        """ Check if there is an AMI for one test. Also check if we are using the env var to force the AMI creation"""
        ami_id = None
        # Configure name
        ami_name = vm.get_cache_name() + "__" + context.scenario.name

        # Check for existing ami
        ami_existing = aws.ec2.get_ami_ids(
            filters=[aws.ec2.GetAmiIdsFilterArgs(name="name", values=[ami_name + "-*"],)], owners=["self"],
        )

        if len(ami_existing.ids) > 0:
            # Latest ami details
            ami_recent = aws.ec2.get_ami(
                filters=[aws.ec2.GetAmiIdsFilterArgs(name="name", values=[ami_name + "-*"],)],
                owners=["self"],
                most_recent=True,
            )
            logger.info(
                f"We found an existing AMI with name {ami_name}: [{ami_recent.id}] and status:[{ami_recent.state}] and expiration: [{ami_recent.deprecation_time}]"
            )
            # The AMI exists. We don't need to create the AMI again
            ami_id = ami_recent.id

            if str(ami_recent.state) != "available":
                logger.info(
                    f"We found an existing AMI but we can no use it because the current status is {ami_recent.state}"
                )
                logger.info("We are not going to create a new AMI and we are not going to use it")
                ami_id = None
                ami_name = None

            # But if we ser env var, created AMI again mandatory (TODO we should destroy previously existing one)
            if os.getenv("AMI_UPDATE") is not None:
                # TODO Pulumi is not prepared to delete resources. Workaround: Import existing ami to pulumi stack, to be deleted when destroying the stack
                # aws.ec2.Ami( ami_existing.name,
                #    name=ami_existing.name,
                #    opts=pulumi.ResourceOptions(import_=ami_existing.id))
                logger.info("We found an existing AMI but AMI_UPDATE is set. We are going to update the AMI")
                ami_id = None

        else:
            logger.info(f"Not found an existing AMI with name {ami_name}")
        return ami_id


class AWSCommander(Commander):
    def create_cache(self, vm, server, last_task):
        """ Create a cache : Create an AMI from the server current status."""
        ami_name = vm.get_cache_name() + "__" + context.scenario.name
        # Ok. All third party software is installed, let's create the ami to reuse it in the future
        logger.info(f"Creating AMI with name [{ami_name}] from instance ")
        # Expiration date for the ami
        # expiration_date = (datetime.now() + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task_dep = aws.ec2.AmiFromInstance(
            ami_name,
            # deprecation_time=expiration_date,
            source_instance_id=server.id,
            opts=pulumi.ResourceOptions(depends_on=[last_task], retain_on_delete=True),
        )
        return task_dep

    def execute_local_command(self, local_command_id, local_command, env, last_task, logger_name):
        last_task = command.local.Command(
            local_command_id,
            create=local_command,
            opts=pulumi.ResourceOptions(depends_on=[last_task]),
            environment=env,
        )
        last_task.stdout.apply(lambda outputlog: pulumi_logger(context.scenario.name, logger_name).info(outputlog))
        return last_task

    def copy_file(self, id, local_path, remote_path, connection, last_task):
        last_task = command.remote.CopyFile(
            id,
            connection=connection,
            local_path=local_path,
            remote_path=remote_path,
            opts=pulumi.ResourceOptions(depends_on=[last_task]),
        )
        return last_task

    def remote_command(
        self, vm, installation_id, remote_command, env, connection, last_task, logger_name=None, output_callback=None
    ):
        cmd_exec_install = command.remote.Command(
            f"-{vm.name}-{installation_id}",
            connection=connection,
            create=remote_command,
            environment=env,
            opts=pulumi.ResourceOptions(depends_on=[last_task]),
        )
        if logger_name:
            cmd_exec_install.stdout.apply(
                lambda outputlog: pulumi_logger(context.scenario.name, logger_name).info(outputlog)
            )
        else:
            # If there isn't logger name specified, we will use the host/ip name to store all the logs of the
            # same remote machine in the same log file
            header = "*****************************************************************"
            Output.all(vm.name, installation_id, remote_command, cmd_exec_install.stdout).apply(
                lambda args: pulumi_logger(context.scenario.name, args[0]).info(
                    f"{header} \n  - COMMAND: {args[1]} \n {header} \n {args[2]} \n\n {header} \n COMMAND OUTPUT \n\n {header} \n {args[3]}"
                )
            )
        if output_callback:
            Output.all(vm, cmd_exec_install.stdout).apply(output_callback)

        return cmd_exec_install

    def remote_copy_folders(
        self, source_folder, destination_folder, command_id, connection, depends_on, relative_path=False
    ):
        # If we don't use remote_path, the remote_path will be a default remote user home
        if not destination_folder:
            destination_folder = os.path.basename(source_folder)

        quee_depends_on = [depends_on]
        for file_name in os.listdir(source_folder):
            # construct full file path
            source = source_folder + "/" + file_name
            destination = destination_folder + "/" + file_name
            logger.debug(f"remote_copy_folders: source:[{source}] and remote destination: [{destination}] ")

            if os.path.isfile(source):
                if not relative_path:
                    destination = os.path.basename(destination)

                logger.debug(f"Copy single file: source:[{source}] and remote destination: [{destination}] ")
                # Launch copy file command
                quee_depends_on.insert(
                    0,
                    command.remote.CopyFile(
                        source + "-" + command_id,
                        connection=connection,
                        local_path=source,
                        remote_path=destination,
                        opts=pulumi.ResourceOptions(depends_on=[quee_depends_on.pop()]),
                    ),
                )
            else:
                # mkdir remote
                if not relative_path:
                    p = pathlib.Path("/" + destination)
                    destination = str(p.relative_to(*p.parts[:2]))
                logger.debug(f"Creating remote folder: {destination}")

                quee_depends_on.insert(
                    0,
                    command.remote.Command(
                        "mkdir-" + destination + "-" + str(uuid.uuid4()) + "-" + command_id,
                        connection=connection,
                        create=f"mkdir -p {destination}",
                        opts=pulumi.ResourceOptions(depends_on=[quee_depends_on.pop()]),
                    ),
                )
                quee_depends_on.insert(
                    0,
                    self.remote_copy_folders(
                        source, destination, command_id, connection, quee_depends_on.pop(), relative_path=True
                    ),
                )
        return quee_depends_on.pop()  # Here the quee should contain only one element
