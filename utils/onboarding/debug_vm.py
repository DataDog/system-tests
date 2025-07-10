import os
from pathlib import Path
import stat
import subprocess
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

        # Upload the logs to S3 only if we are running in gitlab CI/CD
        if "GITLAB_CI" in os.environ:
            # Upload downloaded folder to AWS S3
            execution_unique_identifier = os.getenv("CI_PIPELINE_ID", "datadog-local")
            _upload_to_s3(
                local_base_logs_folder, "system-tests-aws-ssi-apm", execution_unique_identifier, vm.get_vm_unique_id()
            )
            # Check if there are files in the local folder local_base_logs_folder, that are more than 100MB, and delete them.
            # because are uploaded to S3 and we don't want to archive by the CI/CD
            _delete_large_files(local_base_logs_folder)

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


def _delete_large_files(local_folder_path, max_size_mb=100):
    """Delete files larger than max_size_mb from local folder to avoid CI/CD archiving"""
    try:
        max_size_bytes = max_size_mb * 1024 * 1024
        for root, _, files in os.walk(local_folder_path):
            for file in files:
                file_path = Path(root) / file
                if file_path.stat().st_size > max_size_bytes:
                    logger.info(f"Deleting large file ({file_path.stat().st_size / (1024*1024):.1f}MB): {file_path}")
                    file_path.unlink()
    except Exception as e:
        logger.error(f"Error deleting large files: {e}")


def _upload_to_s3(local_folder_path, s3_bucket, s3_folder_prefix, vm_unique_id):
    """Upload a local folder to AWS S3 bucket"""
    try:
        # Extract the last directory name from local_folder_path
        local_path = Path(local_folder_path)
        last_directory = local_path.name

        logger.info(f"Uploading folder to S3 bucket: {s3_bucket}")
        logger.info(f"Local folder: {local_folder_path}")
        logger.info(f"S3 destination: s3://{s3_bucket}/{s3_folder_prefix}/{last_directory}/{vm_unique_id}/")

        # Build the AWS CLI command with the last directory name and vm_unique_id included in S3 path
        s3_destination = f"s3://{s3_bucket}/{s3_folder_prefix}/{last_directory}/{vm_unique_id}/"
        aws_command = ["aws", "s3", "cp", local_folder_path, s3_destination, "--recursive"]

        logger.info(f"Executing AWS CLI command: {' '.join(aws_command)}")

        # Execute the AWS CLI command
        result = subprocess.run(aws_command, capture_output=True, text=True, check=True)

        if result.stdout:
            logger.info(f"AWS CLI output: {result.stdout}")

        # Generate AWS Console URL for the uploaded folder (requires authentication)
        aws_console_url = f"https://s3.console.aws.amazon.com/s3/buckets/{s3_bucket}?region=us-east-1&prefix={s3_folder_prefix}/{last_directory}/{vm_unique_id}/"
        logger.stdout(f"S3 logs URL (AWS Console): {aws_console_url}")

        logger.info(f"Successfully uploaded folder to S3: {s3_destination}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to upload folder to S3: {e}")
        if e.stdout:
            logger.error(f"AWS CLI stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"AWS CLI stderr: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during S3 upload: {e}")
        logger.exception(e)
        raise
