import socket
import os
import subprocess
import vagrant
from fabric.api import env, execute, task, run
from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander
from utils.tools import logger
from utils import context
from utils.onboarding.pulumi_utils import pulumi_logger
from scp import SCPClient


class VagrantProvider(VmProvider):
    def __init__(self):
        super().__init__()
        self.vagrant_machines = []
        self.commander = VagrantCommander()

    def stack_up(self):
        for vm in self.vms:
            logger.stdout(f"--------- Starting Vagrant VM: {vm.name} -----------")
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

            # Install provision on the started server
            self.install_provision(vm, None, client)

    def _set_vm_ports(self, vm):

        conf_file_path = f"{vm.get_log_folder()}/Vagrantfile"
        vm.ssh_config.port = self._get_open_port()
        vm.deffault_open_port = self._get_open_port()
        # qe_arch = "x86_64" if vm.os_cpu == "amd64" else "aarch64"
        # qe.extra_qemu_args = %w(-accel tcg,thread=multi,tb-size=512)
        extra_config = ""
        if vm.os_cpu == "amd64":
            extra_config = f"""
                qe.arch="x86_64"
                qe.machine = "q35"
                qe.cpu = "max"
                qe.smp = "cpus=8,sockets=1,cores=8,threads=1"
                qe.net_device = "virtio-net-pci"       
            """
        port_configuration = f"""
        config.vm.network "forwarded_port", guest: 5985, host: {vm.deffault_open_port}

        config.vm.provider "qemu" do |qe|
            qe.ssh_port={vm.ssh_config.port}
            {extra_config}
        end
        config.vm.synced_folder '.', '/vagrant', disabled: true
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

    def stack_destroy(self):
        logger.info(f"Destroying VMs: {self.vms}")

        for v in self.vagrant_machines:
            v.destroy()


class VagrantCommander(Commander):
    def execute_local_command(self, local_command_id, local_command, env, last_task, logger_name):
        logger.info(f"Vagrant: Execute local command: {local_command}")

        result = subprocess.run(local_command.split(" "), stdout=subprocess.PIPE, env=env)
        pulumi_logger(context.scenario.name, logger_name).info(result.stdout)
        return last_task

    def copy_file(self, id, local_path, remote_path, connection, last_task):

        SCPClient(connection.get_transport()).put(local_path, remote_path)
        return last_task

    def remote_command(
        self, vm, installation_id, remote_command, env, connection, last_task, logger_name=None, output_callback=None
    ):

        logger.debug(f"Running remote-command with installation id: {installation_id}")

        # Workaround with env variables and paramiko :-(
        export_command = ""
        for key, value in env.items():
            export_command += f"export {key}={value} \n "

        # Run the command
        _, stdout, stderr = connection.exec_command(export_command + remote_command)

        # Only combine the error output when we don't have output_callback
        if not output_callback:
            stdout.channel.set_combine_stderr(True)

        # Read the output line by line
        command_output = ""
        for line in stdout.readlines():
            if not line.startswith("export"):
                command_output += line

        if logger_name:
            pulumi_logger(context.scenario.name, logger_name).info(command_output)
        else:
            # If there isn't logger name specified, we will use the host/ip name to store all the logs of the
            # same remote machine in the same log file
            header = "*****************************************************************"
            pulumi_logger(context.scenario.name, vm.name).info(
                f"{header} \n  - COMMAND: {installation_id} \n {header} \n {remote_command} \n\n {header} \n COMMAND OUTPUT \n\n {header} \n {command_output}"
            )

        if output_callback:
            output_callback([vm, command_output])

        return last_task
