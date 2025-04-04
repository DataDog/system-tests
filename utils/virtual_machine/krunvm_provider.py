import sys
import socket
import os
import subprocess
import shutil
import time
import pexpect
import shutil

from utils.virtual_machine.virtual_machine_provider import VmProvider, Commander
from utils._logger import logger
from utils import context
from utils.virtual_machine.vm_logger import vm_logger


class KrunVmProvider(VmProvider):
    """KrunVmProvider is a provider that uses krunvm to create and manage microVMs
    see: https://github.com/containers/krunvm/tree/main
    see: https://slp.prose.sh/running-microvms-on-m1
    """

    def __init__(self):
        super().__init__()
        self.commander = KrunVmCommander()
        self.shared_volume = None
        self.host_project_dir = os.environ.get("SYSTEM_TESTS_HOST_PROJECT_DIR", os.getcwd())
        self._microvm_processes = []

    def _get_container_name(self, microVM_desc):
        """Discover the container name from the microVM description"""
        lines = microVM_desc.split("\n")
        for line in lines:
            if "Buildah" in line:
                return line.replace("Buildah container: ", "")
        return None

    def _image_exists(self, image_name):
        cmd = f" buildah images  --root /Volumes/krunvm/root --runroot /Volumes/krunvm/runroot -f=reference={image_name} | grep {image_name}"
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        stdout, _ = p.communicate()
        if stdout == b"":
            return False
        return True

    def _get_cached_image(self, vm):
        """Check if there is an image for one test. Also check if we are using the env var to force the iamge creation"""
        image_id = None
        # Configure name
        image_name = vm.get_cache_name()
        image_name = image_name.lower()
        image_id = "localhost/" + image_name

        # Check for existing image
        image_existing = self._image_exists(image_id)

        if image_existing:
            logger.info(f"Found an existing image with name {image_name}")

            # But if we set env var, created image again mandatory
            if os.getenv("IMAGE_UPDATE") is not None:
                logger.info(
                    "We found an existing image cache but IMAGE_UPDATE is set. We are going to update the IMAGE"
                )
                image_id = None
        else:
            logger.info(f"Not found an existing cached image with name {image_id}")
            image_id = None
        return image_id

    def stack_up(self):
        logger.stdout(f"--------- Starting Krun VM MicroVM: {self.vm.name} -----------")
        image_id = self._get_cached_image(self.vm)
        # Create the MicroVM
        cmd_create_microvm = f"krunvm create --name {self.vm.name} {self.vm.krunvm_config.oci_image_name if image_id is None else image_id}"
        logger.debug(cmd_create_microvm)
        vm_logger(context.scenario.host_log_folder, self.vm.name).info(cmd_create_microvm)
        output_create_microvm = subprocess.run(cmd_create_microvm.split(), capture_output=True, text=True).stdout
        logger.info(f"[KrumVm] MicroVM created: {output_create_microvm}")

        # Attach volume. Volume is located on the log folder
        path = os.path.join(context.scenario.host_log_folder, self.vm.name)
        os.mkdir(path)
        self.shared_volume = os.path.join(path, "shared_volume")
        os.mkdir(self.shared_volume)
        cmd_krunvm_mount_volume = (
            f"krunvm changevm {self.vm.name} --volume {self.host_project_dir}/{self.shared_volume }:/shared_volume"
        )
        logger.debug(cmd_krunvm_mount_volume)
        vm_logger(context.scenario.host_log_folder, self.vm.name).info(cmd_krunvm_mount_volume)
        output_mount_volume = subprocess.run(cmd_krunvm_mount_volume.split(), capture_output=True, text=True).stdout
        logger.info(f"[KrumVm] MicroVM Share volume mounted: {output_mount_volume}")

        # Copy the init script to the shared volume
        shutil.copyfile("utils/build/virtual_machine/microvm/krunvm_init.sh", f"{self.shared_volume}/krunvm_init.sh")
        os.chmod(f"{self.shared_volume}/krunvm_init.sh", 0o777)

        # Set the shared volume as working directory
        cmd_krunvm_workdir = f"krunvm changevm {self.vm.name} --workdir /shared_volume"
        logger.debug(cmd_krunvm_workdir)
        vm_logger(context.scenario.host_log_folder, self.vm.name).info(cmd_krunvm_workdir)
        output_workdir = subprocess.run(cmd_krunvm_workdir.split(), capture_output=True, text=True).stdout
        logger.info(f"[KrumVm] MicroVM workdir: {output_workdir}")

        # Calculate cache container
        container_name = self._get_container_name(output_workdir)

        # Start the MicroVM and wait for std.in to be ready
        logger.info(f"[KrumVm] MicroVM [{self.vm.name}] starting ...")
        cmd_krunvm_start = f"krunvm start {self.vm.name} /shared_volume/krunvm_init.sh"
        logger.debug(cmd_krunvm_start)
        vm_logger(context.scenario.host_log_folder, self.vm.name).info(f"krunvm start {self.vm.name}")
        microvm_process = pexpect.spawn(cmd_krunvm_start)
        microvm_process.expect("Running krunvm_init.sh")
        logger.info(f"[KrumVm] MicroVM [{self.vm.name}] started.")
        logger.info(microvm_process.after)
        self._microvm_processes.append(microvm_process)

        self.install_provision(self.vm, container_name, None)
        # vm.set_ip("localhost"): Krunvm provides a special networking protocol, some apps may not work with it.
        # Instead of use a network, we can use stdin to lauch commands on the microVM
        self.vm.krunvm_config.stdin = self.commander._get_stdin_path(self.vm)

        self.commander.wait_until_commands_processed(self.vm, timeout=600)

    def stack_destroy(self):
        logger.info(f"Destroying VM: {self.vm}")

        cmd_krunvm_destroy_vm = f"krunvm delete {self.vm.name}"
        logger.debug(cmd_krunvm_destroy_vm)
        output_krunvm_destroy_vm = subprocess.run(cmd_krunvm_destroy_vm.split(), capture_output=True, text=True).stdout
        logger.info(f"[KrumVm] MicroVM [{self.vm.name}] destroyed: {output_krunvm_destroy_vm}")

        for microvm_process in self._microvm_processes:
            microvm_process.close()


class KrunVmCommander(Commander):
    def _get_shared_folder_path(self, vm):
        """Local shared folder path"""
        return os.path.join(context.scenario.host_log_folder, vm.name, "shared_volume")

    def _get_stdin_path(self, vm):
        """Local std.in path: we use std.in to execute commands on the microVM.
        We write the commands to execute on this file and the output is sent to the stod.out file
        """
        return os.path.join(self._get_shared_folder_path(vm), "std.in")

    def create_cache(self, vm, server, last_task):
        """Create a cache : We execute buildah commit to store currebt state of the microVM as an image"""

        # First we need to wait for cacheable commands to be processed
        self.wait_until_commands_processed(vm, timeout=600)

        cache_image_name = vm.get_cache_name()
        cache_image_name = cache_image_name.lower()
        # Ok. All third party software is installed, let's create the ami to reuse it in the future
        logger.info(f"Creating cached image with name [{cache_image_name}] from [{vm.name}] and container [{server}]")
        cache_command = (
            f"buildah commit --root /Volumes/krunvm/root --runroot /Volumes/krunvm/runroot {server} {cache_image_name}"
        )
        logger.debug(cache_command)
        output_cache_creation = subprocess.run(cache_command.split(), capture_output=True, text=True).stdout
        logger.debug(output_cache_creation)

    def execute_local_command(self, local_command_id, local_command, env, last_task, logger_name):
        logger.info(f"KrunVM: Execute local command id: {local_command_id}")
        result = subprocess.run(local_command.split(" "), stdout=subprocess.PIPE, env=env)
        vm_logger(context.scenario.host_log_folder, logger_name).info(result.stdout)
        return last_task

    def copy_file(self, id, local_path, remote_path, connection, last_task, vm=None):
        logger.info(f"KrunVM: copy file from: {local_path} to {remote_path}")
        shutil.copyfile(local_path, os.path.join(self._get_shared_folder_path(vm), remote_path))

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
        # Workaround with env variables  :-(
        export_command = ""
        for key, value in env.items():
            export_command += f"export {key}={value} \n "

        logger.debug(f"Running installation id: {installation_id} ")

        # Store installation commands on script file called as installation_id.sh
        with open(os.path.join(self._get_shared_folder_path(vm), f"{installation_id}.sh"), "a") as script_file:
            script_file.write(f"{export_command} {remote_command.replace('sudo', '')}")

        # Call the installation_id.sh script file from the std.in file
        with open(self._get_stdin_path(vm), "a") as stdin:
            stdin.write(f"bash /shared_volume/{installation_id}.sh\n")

    def wait_until_commands_processed(self, vm, interval=0.1, timeout=1, *args):
        start = time.time()
        time.sleep(1)

        while os.stat(self._get_stdin_path(vm)).st_size != 0 and time.time() - start < timeout:
            time.sleep(interval)

        if os.stat(self._get_stdin_path(vm)).st_size != 0:
            raise TimeoutError("Timed out waiting for condition")

        logger.debug(f"All commands executed on {vm.name}")

    def remote_copy_folders(
        self, source_folder, destination_folder, command_id, connection, depends_on, relative_path=False, vm=None
    ):
        if not source_folder.endswith("/"):
            source_folder = source_folder + "/"

        volume_path = None
        if destination_folder is None or destination_folder in ("", "/"):
            destination_folder = "/"
            volume_path = self._get_shared_folder_path(vm) + "/"
        else:
            volume_path = os.path.join(self._get_shared_folder_path(vm), destination_folder)

        logger.info(f"Copying folder from {source_folder} to {volume_path}")
        shutil.copytree(source_folder, volume_path, dirs_exist_ok=True)
