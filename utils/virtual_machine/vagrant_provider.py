import socket
import vagrant
from fabric.api import env, execute, task, run
from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander
from utils.tools import logger


class VagrantProvider(VmProvider):
    def __init__(self):
        super().__init__()
        self.vagrant_machines = []
        self.commander = VagrantCommander()

    def stack_up(self):
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

            # Install provision on the started server
            self.install_provision(vm, None, client)

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

    def stack_destroy(self):
        logger.info(f"Destroying VMs: {self.vms}")

        for v in self.vagrant_machines:
            if 1 == 1:
                continue
            v.destroy()


class VagrantCommander(Commander):
    def execute_local_command(self, local_command_id, local_command, env, last_task, logger_name):
        raise NotImplementedError

    def copy_file(self, id, local_path, remote_path, connection, last_task):
        raise NotImplementedError

    def remote_command(self, id, remote_command, connection, last_task, logger_name, output_callback=None):
        raise NotImplementedError
