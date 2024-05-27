import socket
import os
import subprocess
import paramiko
from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander
from utils.tools import logger
from utils import context
from utils.virtual_machine.vm_logger import vm_logger


class KrunVmProvider(VmProvider):
    def __init__(self):
        super().__init__()
        self.krunvm_machines = []
        self.commander = KrunVmCommander()

    def stack_up(self):
        for vm in self.vms:
            logger.stdout(f"--------- Starting Krun VM MicroVM: {vm.name} -----------")

            cmd_create_microvm = f"krunvm create --name {vm.name} {vm.krunvm_config.oci_image_name}"
            output_create_microvm = subprocess.run(cmd_create_microvm.split(), capture_output=True, text=True).stdout
            logger.info(f"[KrumVm] MicroVM created: {output_create_microvm}")
            self.commander.start_vm(vm.name)
            # Install provision on the started server
            # self.install_provision(vm, None, client)

    def _get_open_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
        s.close()
        return port

    def stack_destroy(self):
        logger.info(f"Destroying VMs: {self.vms}")

        for v in self.krunvm_machines:
            v.destroy()


class KrunVmCommander(Commander):
    def start_vm(self, kunvm_vm_name):
        import pexpect

        logger.info("[KrumVm] MicroVM starting ...")

        child = pexpect.spawn(f"krunvm start {kunvm_vm_name}")
        child.expect("root@Ubuntu_22_amd64:/#")
        logger.info("[KrumVm] Before ls")
        child.sendline("ls")
        child.logfile = logger.info

        # logger.info(child.before )
        logger.info("[KrumVm] finn")

    def execute_local_command(self, local_command_id, local_command, env, last_task, logger_name):
        logger.info(f"KrunVM: Execute local command: {local_command}")

    def copy_file(self, id, local_path, remote_path, connection, last_task):

        pass

    def remote_command(
        self, vm, installation_id, remote_command, env, connection, last_task, logger_name=None, output_callback=None
    ):

        logger.debug(f"Running remote-command with installation id: {installation_id}")

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
