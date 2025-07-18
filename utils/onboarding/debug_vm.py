from pathlib import Path
import stat
from utils._logger import logger


def download_vm_logs(vm, remote_folder_paths, local_base_logs_folder):
    """Using SSH/SFTP connects to VM and downloads one or more folders from the remote machine

    Args:
        vm: Virtual machine object
        remote_folder_paths: Single path (str) or list of paths (list[str]) to download
        local_base_logs_folder: Base folder where logs will be stored locally

    """
    # Handle both single path and list of paths for backward compatibility
    if isinstance(remote_folder_paths, str):
        remote_folder_paths = [remote_folder_paths]

    try:
        logger.info(f"Downloading folders from machine {vm.get_ip()}")
        logger.info(f"Remote folders: {remote_folder_paths}")

        # Use the VM's get_ssh_connection method instead of creating our own
        c = vm.get_ssh_connection()
        logger.info(f"Connected [{vm.get_ip()}]")

        # Execute docker-compose logs command first to capture container logs
        docker_logs_command = "sudo docker-compose logs > /var/log/datadog_weblog/docker_logs.log 2>&1 || true"
        logger.info(f"Executing remote command: {docker_logs_command}")
        try:
            c.run(docker_logs_command)
            logger.info(f"Docker logs command executed successfully on {vm.get_ip()}")
        except Exception as e:
            logger.warning(f"Failed to execute docker logs command on {vm.get_ip()}: {e}")

        # Create SFTP client
        sftp = c.open_sftp()

        # Download each folder
        for remote_folder_path in remote_folder_paths:
            local_folder_path = f"{local_base_logs_folder}/{remote_folder_path}"
            logger.info(f"Downloading: {remote_folder_path} -> {local_folder_path}")

            # Create local directory if it doesn't exist
            local_path = Path(local_folder_path)
            local_path.mkdir(parents=True, exist_ok=True)

            # Download the folder recursively
            _download_folder_recursive(sftp, remote_folder_path, local_folder_path)

        sftp.close()
        c.close()
        logger.info(f"Successfully downloaded all folders from {vm.get_ip()}")

    except Exception as e:
        logger.error(f"Cannot download folders from remote machine {vm.get_ip()}")
        logger.exception(e)


def _download_folder_recursive(sftp, remote_dir, local_dir):
    """Recursively download a folder using SFTP"""
    try:
        # List contents of remote directory
        for item in sftp.listdir_attr(remote_dir):
            remote_path = f"{remote_dir}/{item.filename}"
            local_path = Path(local_dir) / item.filename

            if stat.S_ISDIR(item.st_mode):
                # Create local directory and recursively download
                local_path.mkdir(exist_ok=True)
                logger.info(f"Created directory: {local_path}")
                _download_folder_recursive(sftp, remote_path, str(local_path))
            else:
                # Download file
                logger.info(f"Downloading file: {remote_path} -> {local_path}")
                sftp.get(remote_path, str(local_path))

    except Exception as e:
        logger.error(f"Error downloading from {remote_dir}")
        logger.exception(e)
