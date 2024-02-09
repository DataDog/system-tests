from utils.tools import logger
from pulumi import automation as auto
from utils.onboarding.pulumi_ssh import PulumiSSH
import pulumi
import pulumi_aws as aws
from pulumi import Output
import pulumi_command as command
from utils.onboarding.pulumi_ssh import PulumiSSH
from utils.onboarding.pulumi_utils import remote_install, pulumi_logger

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

    def configure(self, required_vms, vm_provision):
        self.vms = required_vms
        self.provision = vm_provision

    def start(self):
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

    def destroy(self):
        logger.info(f"Destroying VMs: {self.vms}")

    def _start_vm(self, vm):
        # Startup VM and prepare connection
        ec2_server = aws.ec2.Instance(
            vm.name,
            instance_type=vm.aws_config.ami_instance_type,
            vpc_security_group_ids=vm.aws_config.aws_infra_config.vpc_security_group_ids,
            subnet_id=vm.aws_config.aws_infra_config.subnet_id,
            key_name=PulumiSSH.keypair_name,
            ami=vm.aws_config.ami_id,
            tags={"Name": vm.name,},
            opts=PulumiSSH.aws_key_resource,
        )
        Output.all(ec2_server.private_ip).apply(lambda args: vm.set_ip(args[0]))
        vm.ssh_config.pkey = paramiko.RSAKey.from_private_key_file(PulumiSSH.pem_file)
        vm.ssh_config.username = vm.aws_config._user


provider_factory = VmProviderFactory()
