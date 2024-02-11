from utils.tools import logger
from pulumi import automation as auto
from utils.onboarding.pulumi_ssh import PulumiSSH
import pulumi
import pulumi_aws as aws
from pulumi import Output
import pulumi_command as command
from utils.onboarding.pulumi_ssh import PulumiSSH
from utils.onboarding.pulumi_utils import pulumi_logger

import vagrant
from fabric.api import env, execute, task, run
import subprocess
from io import StringIO
import paramiko
from utils import context
import os
import socket


class VmProviderFactory:
    def get_provider(self, provider_id):
        logger.info(f"Using {provider_id} provider")
        if provider_id == "aws":
            return AWSPulumiProvider()
        elif provider_id == "vagrant":
            return VagrantProvider()
        else:
            raise ValueError("Not supported provided", provider_id)


class _VmProvider:
    def __init__(self):
        self.vms = None
        self.provision = None

    def configure(self, required_vms):
        self.vms = required_vms

    def start(self):
        raise NotImplementedError

    def install_provision(self, vm):
        raise NotImplementedError

    def destroy(self):
        raise NotImplementedError


class VagrantProvider(_VmProvider):
    def __init__(self):
        super().__init__()
        self.vagrant_machines = []

    def start(self):
        for vm in self.vms:
            logger.info(f"--------- Starting Vagrant VM: {vm.name} -----------")
            if 1 == 1:
                continue
            log_cm = vagrant.make_file_cm(vm.get_default_log_file())
            v = vagrant.Vagrant(root=vm.get_log_folder(), out_cm=log_cm, err_cm=log_cm)
            v.init(box_name=vm.vagrant_config.box_name)
            self._set_vm_ports(vm)

            v.up(provider="qemu")
            env.hosts = [v.user_hostname_port()]
            env.key_filename = v.keyfile()
            env.disable_known_hosts = True
            logger.info(f"VMs started: {v.user_hostname_port()} - {v.keyfile()}")
            vm.set_ip(v.hostname())
            vm.ssh_config.key_filename = v.keyfile()
            vm.ssh_config.username = v.user()

            client = vm.ssh_config.get_ssh_connection()
            logger.info(f"Connected to VMs: {v.user_hostname_port()} - {v.keyfile()}")
            _, stdout, stderr = client.exec_command("echo 'HOLLLLLLLLAAAAAAAAAAAAA'")
            logger.info("Command output:")
            logger.info(stdout.readlines())
            logger.info("Command err output:")
            logger.info(stderr.readlines())
            self.vagrant_machines.append(v)

    def _set_vm_ports(self, vm):

        conf_file_path = f"{vm.get_log_folder()}/Vagrantfile"
        vm.ssh_config.port = self._get_open_port()
        port_configuration = f"""
        config.vm.provider "qemu" do |qe|
            qe.ssh_port={vm.ssh_config.port}
        end
        end
        """
        lines = []
        with open(conf_file_path, "r") as conf_file:
            lines = conf_file.readlines()[:-1]
        lines.append(port_configuration)
        with open(conf_file_path, "w") as conf_file:
            conf_file.writelines(lines)

    def _get_open_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port

    def destroy(self):
        logger.info(f"Destroying VMs: {self.vms}")

        for v in self.vagrant_machines:
            if 1 == 1:
                continue
            v.destroy()


class AWSPulumiProvider(_VmProvider):
    def start(self):
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
            #   self.stack.set_config("aws:SkipMetadataApiCheck", auto.ConfigValue("false"))
            up_res = self.stack.up(on_output=logger.info)
        except Exception as pulumi_exception:  #
            logger.error("Exception launching aws provision infraestructure")
            logger.exception(pulumi_exception)

    def install_provision(self, vm, ec2_server, create_cache=False):
        server_connection = command.remote.ConnectionArgs(
            host=ec2_server.private_ip,
            user=vm.aws_config.user,
            private_key=PulumiSSH.private_key_pem,
            dial_error_limit=-1,
        )
        provision = vm.get_provision()

        last_task = ec2_server
        if create_cache:
            # First install cacheable installations
            for installation in provision.installations:
                if installation.cache:
                    logger.info(f"Installing {installation.id} in {vm.name}")
                    last_task = self._remote_install(server_connection, vm, last_task, installation)

            # Then install lang variant if needed (cacheable)
            if provision.lang_variant_installation:
                last_task = self._remote_install(server_connection, vm, last_task, provision.lang_variant_installation)
            last_task = self._create_ami(vm, ec2_server, last_task)

        # Then install non cacheable installations
        for installation in provision.installations:
            if not installation.cache:
                logger.info(f"Installing no cacheable {installation.id} in {vm.name}")
                last_task = self._remote_install(server_connection, vm, last_task, installation)

        # Extract tested/installed components
        logger.info(f"Extracting {provision.tested_components_installation.id} in {vm.name}")

        output_callback = lambda args: args[0].set_tested_components(args[1])
        last_task = self._remote_install(
            server_connection,
            vm,
            last_task,
            provision.tested_components_installation,
            logger_name="tested_components",
            output_callback=output_callback,
        )

        # Finally install weblog
        logger.info(f"Installing {provision.weblog_installation.id} in {vm.name}")
        last_task = self._remote_install(server_connection, vm, last_task, provision.weblog_installation)

    def _remote_install(self, server_connection, vm, last_task, installation, logger_name=None, output_callback=None):

        local_command = None
        # Execute local command if we need
        if installation.local_command:
            local_command = installation.local_command

        # Execute local script if we need
        if installation.local_script:
            local_command = "sh " + installation.local_script

        if local_command:
            last_task = command.local.Command(
                f"local-script_{vm.name}_{installation.id}",
                create=local_command,
                opts=pulumi.ResourceOptions(depends_on=[last_task]),
                environment=self._get_command_environment(vm),
            )
            last_task.stdout.apply(lambda outputlog: pulumi_logger(context.scenario.name, vm.name).info(outputlog))

        # Copy files from local to remote if we need
        if installation.copy_files:
            for file_to_copy in installation.copy_files:

                # If we don't use remote_path, the remote_path will be a default remote user home
                if file_to_copy.remote_path:
                    remote_path = file_to_copy.remote_path
                else:
                    remote_path = os.path.basename(file_to_copy.local_path)

                if not os.path.isdir(file_to_copy.local_path):
                    # If the local path contains a variable, we need to replace it
                    for key, value in self._get_command_environment(vm).items():
                        file_to_copy.local_path = file_to_copy.local_path.replace(f"${key}", value)
                        remote_path = remote_path.replace(f"${key}", value)

                    logger.debug(f"Copy file from {file_to_copy.local_path} to {remote_path}")
                    # Launch copy file command
                    last_task = command.remote.CopyFile(
                        file_to_copy.name + f"-{vm.name}-{installation.id}",
                        connection=server_connection,
                        local_path=file_to_copy.local_path,
                        remote_path=remote_path,
                        opts=pulumi.ResourceOptions(depends_on=[last_task]),
                    )
                else:
                    raise NotImplementedError(f"Copy folders not implemented {file_to_copy.local_path}")

        # Execute a basic command on our server.
        cmd_exec_install = command.remote.Command(
            f"-{vm.name}-{installation.id}",
            connection=server_connection,
            create=installation.remote_command,
            opts=pulumi.ResourceOptions(depends_on=[last_task]),
            environment=self._get_command_environment(vm),
        )

        if logger_name:
            cmd_exec_install.stdout.apply(
                lambda outputlog: pulumi_logger(context.scenario.name, logger_name).info(outputlog)
            )
        else:
            # If there isn't logger name specified, we will use the host/ip name to store all the logs of the
            # same remote machine in the same log file
            header = "*****************************************************************"
            Output.all(vm.name, installation.id, installation.remote_command, cmd_exec_install.stdout).apply(
                lambda args: pulumi_logger(context.scenario.name, args[0]).info(
                    f"{header} \n  - COMMAND: {args[1]} \n {header} \n {args[2]} \n\n {header} \n COMMAND OUTPUT \n\n {header} \n {args[3]}"
                )
            )
        if output_callback:
            # cmd_exec_install.stdout.apply(output_callback)
            Output.all(vm, cmd_exec_install.stdout).apply(output_callback)

        return cmd_exec_install

    def _get_command_environment(self, vm):
        command_env = {}
        for key, value in vm.get_provision().env.items():
            command_env["DD_" + key] = value
        # DD
        command_env["DD_API_KEY"] = vm.datadog_config.dd_api_key
        command_env["DD_APP_KEY"] = vm.datadog_config.dd_app_key
        # Docker
        if vm.datadog_config.docker_login:
            command_env["DD_DOCKER_LOGIN"] = vm.datadog_config.docker_login
            command_env["DD_DOCKER_LOGIN_PASS"] = vm.datadog_config.docker_login_pass
        # Tested library
        command_env["DD_LANG"] = command_env["DD_LANG"] if command_env["DD_LANG"] != "nodejs" else "js"
        # VM name
        command_env["DD_VM_NAME"] = vm.name
        return command_env

    def destroy(self):
        logger.info(f"Destroying VMs: {self.vms}")
        self.stack.destroy(on_output=logger.info)

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
        Output.all(vm, ec2_server.private_ip).apply(lambda args: args[0].set_ip(args[1]))
        pulumi.export("privateIp_" + vm.name, ec2_server.private_ip)
        Output.all(ec2_server.private_ip, vm.name).apply(
            lambda args: pulumi_logger(context.scenario.name, "vms_desc").info(f"{args[0]}:{args[1]}")
        )
        vm.ssh_config.pkey = paramiko.RSAKey.from_private_key_file(PulumiSSH.pem_file)
        vm.ssh_config.username = vm.aws_config.user

        self.install_provision(vm, ec2_server, create_cache=ami_id is None)

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

    def _create_ami(self, vm, ec2_server, task_dep):

        ami_name = vm.get_cache_name() + "__" + context.scenario.name
        # Ok. All third party software is installed, let's create the ami to reuse it in the future
        logger.info(f"Creating AMI with name [{ami_name}] from instance ")
        # Expiration date for the ami
        # expiration_date = (datetime.now() + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task_dep = aws.ec2.AmiFromInstance(
            ami_name,
            # deprecation_time=expiration_date,
            source_instance_id=ec2_server.id,
            opts=pulumi.ResourceOptions(depends_on=[task_dep], retain_on_delete=True),
        )
        return task_dep


provider_factory = VmProviderFactory()
