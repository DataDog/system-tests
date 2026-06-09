from pathlib import Path
import stat
from paramiko.sftp_client import SFTPClient
from utils._logger import logger
from utils.virtual_machine.virtual_machines import _VirtualMachine

# Collect dd-agent docker diagnostics into /var/log/datadog_weblog (runs from VM user home).
_COLLECT_DD_AGENT_DIAGNOSTICS_CMD = r"""bash -lc '
sudo mkdir -p /var/log/datadog_weblog && sudo chmod 777 /var/log/datadog_weblog;
cd ~;
if [ -f "$HOME/dd-agent-diagnostics.log" ]; then
  sudo cp "$HOME/dd-agent-diagnostics.log" /var/log/datadog_weblog/dd-agent-diagnostics.log 2>/dev/null || true;
fi;
if [ -f docker-compose-agent-prod.yml ]; then
{
echo "..:: DD-AGENT DIAGNOSTICS (download_vm_logs) ::..";
date -u "+%Y-%m-%dT%H:%M:%SZ";
sudo docker-compose -f docker-compose-agent-prod.yml ps 2>&1 || true;
if sudo docker inspect dd-agent >/dev/null 2>&1; then
echo "..:: DD-AGENT HEALTH ::..";
sudo docker inspect dd-agent --format "{{json .State.Health}}" 2>&1 || true;
echo "..:: DD-AGENT LOGS (docker logs) ::..";
sudo docker logs dd-agent 2>&1 | tail -300 || true;
else echo "..:: dd-agent container not found ::.."; sudo docker ps -a 2>&1 || true;
fi;
echo "..:: DD-AGENT LOGS (docker-compose logs) ::..";
sudo docker-compose -f docker-compose-agent-prod.yml logs --no-color datadog 2>&1 || true;
} | sudo tee /var/log/datadog_weblog/dd-agent-diagnostics.log >/dev/null;
fi'"""


def download_vm_logs(vm: _VirtualMachine, remote_folder_paths: list[str], local_base_logs_folder: str) -> bool:
    """Connect over SSH/SFTP and download folders from the remote machine.

    Works even when provisioning failed (uses get_ssh_connection_for_log_download).

    Returns True if at least one folder was downloaded successfully.
    """
    if isinstance(remote_folder_paths, str):
        remote_folder_paths = [remote_folder_paths]

    if not vm.ssh_config.hostname:
        logger.warning(
            "Skipping VM log download for %s: no IP/hostname (VM may not have been created)",
            vm.name,
        )
        return False

    downloaded_any = False
    try:
        logger.info(
            "Downloading folders from machine %s (%s) provision_error=%s",
            vm.name,
            vm.ssh_config.hostname,
            vm.provision_install_error is not None,
        )
        logger.info("Remote folders: %s", remote_folder_paths)

        connection = vm.get_ssh_connection_for_log_download()
        logger.info("Connected [%s]", vm.ssh_config.hostname)

        commands_to_run = [
            "sudo mkdir -p /var/log/datadog_weblog || true",
            "sudo chmod 777 /var/log/datadog_weblog || true",
            _COLLECT_DD_AGENT_DIAGNOSTICS_CMD,
            # Docker and systemd related logs (mirrors auto-inject-vm_logs.yml)
            "bash -lc 'cd ~ && sudo docker-compose ps > /var/log/datadog_weblog/docker_proccess.log 2>&1 || true'",
            "bash -lc 'cd ~ && sudo docker-compose logs > /var/log/datadog_weblog/docker_logs.log 2>&1 || true'",
            "sudo journalctl -xeu docker > /var/log/datadog_weblog/journalctl_docker.log 2>&1 || true",
            "sudo cp /etc/datadog-agent/application_monitoring.yaml /var/log/datadog_weblog/application_monitoring.yaml 2>&1 || true",
            "sudo cat /var/log/cloud-init.log > /var/log/datadog_weblog/cloud-init.log 2>&1 || true",
            "sudo cat /var/log/syslog > /var/log/datadog_weblog/syslog.log 2>&1 || true",
            "sudo dmesg > /var/log/datadog_weblog/dmesg.log 2>&1 || true",
            "sudo systemctl list-dependencies docker.service > /var/log/datadog_weblog/docker_list_dependencies.log 2>&1 || true",
            "sudo systemctl list-timers --all > /var/log/datadog_weblog/system.timers.log 2>&1 || true",
            "sudo crontab -l > /var/log/datadog_weblog/crontab.log 2>&1 || true",
            "sudo cat /var/log/apt/history.log > /var/log/datadog_weblog/apt.log 2>&1 || true",
            "sudo cat /var/log/yum.log > /var/log/datadog_weblog/yum.log 2>&1 || true",
        ]

        for cmd in commands_to_run:
            try:
                logger.info("Executing remote command: %s", cmd)
                _stdin, stdout, _stderr = connection.exec_command(cmd)
                exit_status = stdout.channel.recv_exit_status()
                logger.info("Remote command exit status: %s", exit_status)
            except Exception as exec_err:
                logger.warning("Failed executing command on %s: %s", vm.ssh_config.hostname, cmd)
                logger.exception(exec_err)

        sftp = connection.open_sftp()

        for remote_folder_path in remote_folder_paths:
            local_folder_path = f"{local_base_logs_folder}/{remote_folder_path}"
            logger.info("Downloading: %s -> %s", remote_folder_path, local_folder_path)

            local_path = Path(local_folder_path)
            local_path.mkdir(parents=True, exist_ok=True)

            if _download_folder_recursive(sftp, remote_folder_path, local_folder_path):
                downloaded_any = True

        sftp.close()
        connection.close()
        if downloaded_any:
            logger.info(
                "Successfully downloaded VM logs from %s into %s", vm.ssh_config.hostname, local_base_logs_folder
            )
        else:
            logger.warning("No files downloaded from %s", vm.ssh_config.hostname)

    except Exception:
        logger.exception("Cannot download folders from remote machine %s", vm.name)

    return downloaded_any


def _download_folder_recursive(sftp: SFTPClient, remote_dir: str, local_dir: str) -> bool:
    """Recursively download a folder using SFTP. Returns True if at least one file was downloaded."""
    downloaded_any = False
    try:
        for item in sftp.listdir_attr(remote_dir):
            remote_path = f"{remote_dir}/{item.filename}"
            local_path = Path(local_dir) / item.filename

            if stat.S_ISDIR(item.st_mode):
                local_path.mkdir(exist_ok=True)
                logger.info("Created directory: %s", local_path)
                if _download_folder_recursive(sftp, remote_path, str(local_path)):
                    downloaded_any = True
            else:
                logger.info("Downloading file: %s -> %s", remote_path, local_path)
                sftp.get(remote_path, str(local_path))
                downloaded_any = True

    except Exception:
        logger.exception("Error downloading from %s", remote_dir)

    return downloaded_any
