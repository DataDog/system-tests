import sys
import socket
import os
import subprocess
import shutil
import time
import pexpect
import shutil

from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander
from utils.tools import logger
from utils import context
from utils.virtual_machine.vm_logger import vm_logger


class KrunVmProvider(VmProvider):
    def __init__(self):
        super().__init__()
        self.commander = KrunVmCommander()
        self.shared_volume = None
        self.host_project_dir = os.environ.get("SYSTEM_TESTS_HOST_PROJECT_DIR", os.getcwd())
        self._microvm_processes = []

    def stack_up(self):
        for vm in self.vms:
            logger.stdout(f"--------- Starting Krun VM MicroVM: {vm.name} -----------")
            # Create the MicroVM
            cmd_create_microvm = f"krunvm create --name {vm.name} {vm.krunvm_config.oci_image_name}"
            logger.debug(cmd_create_microvm)
            output_create_microvm = subprocess.run(cmd_create_microvm.split(), capture_output=True, text=True).stdout
            logger.info(f"[KrumVm] MicroVM created: {output_create_microvm}")

            # Attach volume. Volume is located on the log folder
            path = os.path.join(context.scenario.host_log_folder, vm.name)
            os.mkdir(path)
            self.shared_volume = os.path.join(path, "shared_volume")
            os.mkdir(self.shared_volume)
            cmd_krunvm_mount_volume = (
                f"krunvm changevm {vm.name} --volume {self.host_project_dir}/{self.shared_volume }:/shared_volume"
            )
            logger.debug(cmd_krunvm_mount_volume)
            output_mount_volume = subprocess.run(cmd_krunvm_mount_volume.split(), capture_output=True, text=True).stdout
            logger.info(f"[KrumVm] MicroVM Share volume mounted: {output_mount_volume}")

            # Open http port
            cmd_krunvm_open_ports = f"krunvm changevm {vm.name} --port 5985:5985"
            logger.debug(cmd_krunvm_open_ports)
            output_open_ports = subprocess.run(cmd_krunvm_open_ports.split(), capture_output=True, text=True).stdout
            logger.info(f"[KrumVm] MicroVM port open: {output_open_ports}")

            # Copy the init script to the shared volume
            shutil.copyfile(
                "utils/build/virtual_machine/microvm/krunvm_init.sh", f"{self.shared_volume}/krunvm_init.sh"
            )
            os.chmod(f"{self.shared_volume}/krunvm_init.sh", 0o777)

            # Start the MicroVM and wait for std.in to be ready
            logger.info(f"[KrumVm] MicroVM [{vm.name}] starting ...")
            cmd_krunvm_start = f"krunvm start {vm.name} /shared_volume/krunvm_init.sh"
            logger.debug(cmd_krunvm_start)
            microvm_process = pexpect.spawn(cmd_krunvm_start)
            microvm_process.expect("Running krunvm_init.sh")
            logger.info(f"[KrumVm] MicroVM [{vm.name}] started.")
            logger.info(microvm_process.after)
            self._microvm_processes.append(microvm_process)
            # time.sleep(10)
            self.install_provision(vm, None, None)
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

        for v in self.vms:
            cmd_krunvm_destroy_vm = f"krunvm delete {v.name}"
            logger.debug(cmd_krunvm_destroy_vm)
            output_krunvm_destroy_vm = subprocess.run(
                cmd_krunvm_destroy_vm.split(), capture_output=True, text=True
            ).stdout
            logger.info(f"[KrumVm] MicroVM [{v.name}] destroyed: {output_krunvm_destroy_vm}")

        for microvm_process in self._microvm_processes:
            microvm_process.close()


class KrunVmCommander(Commander):
    def _get_shared_folder_path(self, vm):
        return os.path.join(context.scenario.host_log_folder, vm.name, "shared_volume")

    def _get_stdin_path(self, vm):
        return os.path.join(self._get_shared_folder_path(vm), "std.in")

    def execute_local_command(self, local_command_id, local_command, env, last_task, logger_name):
        logger.info(f"KrunVM: Execute local command: {local_command}")

    def copy_file(self, id, local_path, remote_path, connection, last_task, vm=None):
        logger.info(f"KrunVM: copy file from: {local_path} to {remote_path}")
        shutil.copyfile(local_path, os.path.join(self._get_shared_folder_path(vm), remote_path))

    def remote_command(
        self, vm, installation_id, remote_command, env, connection, last_task, logger_name=None, output_callback=None
    ):
        # Workaround with env variables and paramiko :-(
        export_command = ""
        for key, value in env.items():
            export_command += f"export {key}={value} \n "

        logger.debug(f"Running installation id: {installation_id} ")
        logger.debug(f"Remote command: {export_command} {remote_command}")

        # Store installation commands on script file called as installation_id.sh
        with open(os.path.join(self._get_shared_folder_path(vm), f"{installation_id}.sh"), "a") as script_file:
            script_file.write(f"{export_command} {remote_command.replace('sudo', '')}")

        # Call the installation_id.sh script file from the std.in file
        with open(self._get_stdin_path(vm), "a") as stdin:
            stdin.write(f"bash /shared_volume/{installation_id}.sh\n")

        self.wait_until_commands_processed(vm, timeout=300)

    def wait_until_commands_processed(self, vm, interval=0.1, timeout=1, *args):
        start = time.time()
        time.sleep(1)

        while os.stat(self._get_stdin_path(vm)).st_size != 0 and time.time() - start < timeout:
            time.sleep(interval)

        if os.stat(self._get_stdin_path(vm)).st_size != 0:
            raise TimeoutError("Timed out waiting for condition")

        logger.debug(f"All commands executed on {vm.name}")

    def remote_copy_folders(
        self, source_folder, destination_folder, command_id, connection, depends_on, relative_path=False
    ):
        if not source_folder.endswith("/"):
            source_folder = source_folder + "/"

        if destination_folder is None or destination_folder == "":
            destination_folder = "./"
        #    sftp = MySFTPClient.from_transport(connection.get_transport())
        #    sftp.mkdir(destination_folder, ignore_existing=True)
        #    sftp.put_dir(source_folder, destination_folder)
        #    sftp.close()
        logger.info(f"Copying folder {source_folder} to {destination_folder}")
