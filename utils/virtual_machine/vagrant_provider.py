import socket
import os
import subprocess
import vagrant
import paramiko
from fabric.api import env
from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander
from utils.tools import logger
from utils import context
from scp import SCPClient
from utils.virtual_machine.vm_logger import vm_logger


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
            # TODO Support for different vagrant providers. Currently only support for qemu
            self._set_vagrant_configuration(vm)
            v.up(provider="qemu")
            self.vagrant_machines.append(v)
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

    def _set_vagrant_configuration(self, vm):
        """ Makes some configuration on the vagrant files
        These configurations are relative to the provider and to port forwarding (for weblog) and port for ssh 
        TODO Support for different vagrant providers. Currently only support for qemu
        """

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
        vm_logger(context.scenario.name, logger_name).info(result.stdout)
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
            vm_logger(context.scenario.name, logger_name).info(command_output)
        else:
            # If there isn't logger name specified, we will use the host/ip name to store all the logs of the
            # same remote machine in the same log file
            header = "*****************************************************************"
            vm_logger(context.scenario.name, vm.name).info(
                f"{header} \n  - COMMAND: {installation_id} \n {header} \n {remote_command} \n\n {header} \n COMMAND OUTPUT \n\n {header} \n {command_output}"
            )

        if output_callback:
            output_callback([vm, command_output])

        return last_task

    def remote_copy_folders(
        self, source_folder, destination_folder, command_id, connection, depends_on, relative_path=False
    ):
        if not source_folder.endswith("/"):
            source_folder = source_folder + "/"

        if destination_folder is None or destination_folder == "":
            destination_folder = "./"
        sftp = MySFTPClient.from_transport(connection.get_transport())
        sftp.mkdir(destination_folder, ignore_existing=True)
        sftp.put_dir(source_folder, destination_folder)
        sftp.close()


class MySFTPClient(paramiko.SFTPClient):
    def put_dir(self, source, target):
        """ Uploads the contents of the source directory to the target path. The
            target directory needs to exists. All subdirectories in source are 
            created under target.
        """
        for item in os.listdir(source):
            if os.path.isfile(os.path.join(source, item)):
                self.put(os.path.join(source, item), "%s/%s" % (target, item))
            else:
                self.mkdir("%s/%s" % (target, item), ignore_existing=True)
                self.put_dir(os.path.join(source, item), "%s/%s" % (target, item))

    def mkdir(self, path, mode=511, ignore_existing=False):
        """ Augments mkdir by adding an option to not fail if the folder exists  """
        try:
            super(MySFTPClient, self).mkdir(path, mode)
        except IOError:
            if ignore_existing:
                pass
            else:
                raise
