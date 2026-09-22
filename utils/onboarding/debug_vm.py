from pathlib import Path
import stat
from paramiko.client import SSHClient
from paramiko.sftp_client import SFTPClient
from utils._logger import logger
from utils.virtual_machine.virtual_machines import _VirtualMachine

# Preserve the startup diagnostics and append a fresh Agent snapshot at log-download time.
# The final snapshot covers delayed profiler uploads that happen after the app provision completes.
_COLLECT_DD_AGENT_DIAGNOSTICS_CMD = r"""bash -lc '
set +e
sudo mkdir -p /var/log/datadog_weblog && sudo chmod 777 /var/log/datadog_weblog;
cd ~;
if [ -f "$HOME/dd-agent-diagnostics.log" ]; then
  sudo cp "$HOME/dd-agent-diagnostics.log" /var/log/datadog_weblog/dd-agent-diagnostics.log 2>/dev/null || true;
else
  sudo touch /var/log/datadog_weblog/dd-agent-diagnostics.log;
fi
if grep -qx "SYSTEM_TESTS_PROFILING_DEBUG=1" "$HOME/scenario_app.env" 2>/dev/null &&
  sudo docker inspect dd-agent >/dev/null 2>&1; then
  {
    echo "..:: DD-AGENT FINAL DIAGNOSTICS ::..";
    date -u "+%Y-%m-%dT%H:%M:%SZ";
    sudo docker-compose -f docker-compose-agent-prod.yml ps 2>&1 || true;
    sudo docker inspect dd-agent --format "{{json .State.Health}}" 2>&1 || true;
    sudo docker logs --since 15m --timestamps dd-agent 2>&1 || true;
  } | sudo tee -a /var/log/datadog_weblog/dd-agent-diagnostics.log >/dev/null;
fi
sudo chmod 644 /var/log/datadog_weblog/dd-agent-diagnostics.log 2>/dev/null || true;
'"""

# Capture evidence from the real PHP server process rather than from a helper `php -v` process.
_COLLECT_PHP_PROCESS_DIAGNOSTICS_CMD = r"""bash -lc '
set +e
dest=/var/log/datadog_weblog
sudo mkdir -p "$dest"
sudo chmod 777 "$dest"
if ! grep -qx "SYSTEM_TESTS_PROFILING_DEBUG=1" "$HOME/scenario_app.env" 2>/dev/null; then
  exit 0
fi
if ! sudo docker inspect test-app >/dev/null 2>&1; then
  exit 0
fi
process_table="$(sudo docker top test-app -eo pid,ppid,comm,args 2>&1)"
php_pid="$(printf "%s\n" "${process_table}" | awk "NR > 1 && \$3 ~ /^php/ {print \$1; exit}")"
if [ -z "${php_pid}" ]; then
  exit 0
fi
{
  echo "..:: PHP SERVER PROCESS DIAGNOSTICS ::.."
  date -u "+%Y-%m-%dT%H:%M:%SZ"
  echo "..:: CONTAINER STATE ::.."
  sudo docker inspect test-app --format "{{json .State}}" 2>&1 || true
  echo "..:: PROCESS TABLE ::.."
  printf "%s\n" "${process_table}"
  echo "..:: PHP PID ::.."
  printf "%s\n" "${php_pid}"
  echo "..:: COMMAND LINE ::.."
  sudo sh -c "tr '\\0' ' ' < /proc/${php_pid}/cmdline" 2>/dev/null
  printf "\n"
  echo "..:: DD ENVIRONMENT (SECRETS REDACTED) ::.."
  sudo sh -c "tr '\\0' '\\n' < /proc/${php_pid}/environ" 2>/dev/null |
    awk -F= "/^DD_/ {key=\$1; if (key ~ /(KEY|TOKEN|PASS|SECRET)/) print key \"=<redacted>\"; else print}" |
    sort
  echo "..:: PROFILER THREADS ::.."
  for comm in /proc/"${php_pid}"/task/*/comm; do
    [ -r "${comm}" ] && sudo cat "${comm}"
  done | sort -u
  echo "..:: DATADOG LIBRARY MAPPINGS ::.."
  sudo grep -E "datadog-profiling|libdatadog_php|ddtrace" "/proc/${php_pid}/maps" 2>/dev/null || true
  echo "..:: APPLICATION MONITORING CONFIG ::.."
  sudo docker exec test-app cat /etc/datadog-agent/application_monitoring.yaml 2>&1 || true
} > "$dest/php-process-diagnostics.log" 2>&1
sudo chmod 644 "$dest/php-process-diagnostics.log" 2>/dev/null || true
'"""

# Collect core dumps into /var/log/datadog_weblog so SFTP download can retrieve them.
# Host PHP apps (profiling in particular) can segfault; cores may land in cwd, systemd-coredump,
# or the weblog log dir depending on kernel.core_pattern.
_COLLECT_CORE_DUMPS_CMD = r"""bash -lc '
set +e
dest=/var/log/datadog_weblog
sudo mkdir -p "$dest"
sudo chmod 777 "$dest"
{
  echo "core_pattern: $(cat /proc/sys/kernel/core_pattern 2>/dev/null || echo unknown)"
  echo "suid_dumpable: $(cat /proc/sys/fs/suid_dumpable 2>/dev/null || echo unknown)"
  echo "core ulimit: $(ulimit -c)"
} | sudo tee "$dest/core-diagnostics.txt" >/dev/null
if command -v coredumpctl >/dev/null 2>&1; then
  sudo coredumpctl list > "$dest/coredumpctl-list.txt" 2>&1 || true
  sudo coredumpctl -1 dump --output="$dest/systemd-coredump" >/dev/null 2>&1 || true
fi
for dir in /var/log/datadog_weblog /home/datadog /tmp /var/crash /var/lib/systemd/coredump "$HOME"; do
  [ -d "$dir" ] || continue
  find "$dir" -maxdepth 1 -type f \( -name core -o -name "core.*" -o -name "core-*" \) 2>/dev/null |
    while read -r core; do
      case "$core" in
        /var/log/datadog_weblog/*)
          sudo chmod a+r "$core" 2>/dev/null || true
          echo "found $core" | sudo tee -a "$dest/core-diagnostics.txt" >/dev/null
          continue
          ;;
      esac
      target="$dest/$(basename "$core")"
      sudo cp "$core" "$target" 2>/dev/null || true
      sudo chmod a+r "$target" 2>/dev/null || true
      echo "copied $core -> $target" | sudo tee -a "$dest/core-diagnostics.txt" >/dev/null
    done
done
sudo journalctl -xeu test-app.service > "$dest/journalctl_test-app.log" 2>&1 || true
sudo chmod -R a+rX /var/log/datadog_weblog 2>/dev/null || true
'"""

# Remote commands that collect host/docker/agent logs into /var/log/datadog_weblog before download.
# Mirrors utils/build/virtual_machine/provisions/auto-inject/auto-inject-vm_logs.yml.
_LOG_COLLECTION_COMMANDS = [
    "sudo mkdir -p /var/log/datadog_weblog || true",
    "sudo chmod 777 /var/log/datadog_weblog || true",
    _COLLECT_CORE_DUMPS_CMD,
    _COLLECT_PHP_PROCESS_DIAGNOSTICS_CMD,
    _COLLECT_DD_AGENT_DIAGNOSTICS_CMD,
    "bash -lc 'cd ~ && sudo docker-compose ps > /var/log/datadog_weblog/docker_proccess.log 2>&1 || true'",
    "bash -lc 'cd ~ && sudo docker-compose logs > /var/log/datadog_weblog/docker_logs.log 2>&1 || true'",
    "sudo journalctl -xeu docker > /var/log/datadog_weblog/journalctl_docker.log 2>&1 || true",
    (
        "sudo cp /etc/datadog-agent/application_monitoring.yaml "
        "/var/log/datadog_weblog/application_monitoring.yaml 2>&1 || true"
    ),
    "sudo cat /var/log/cloud-init.log > /var/log/datadog_weblog/cloud-init.log 2>&1 || true",
    "sudo cat /var/log/syslog > /var/log/datadog_weblog/syslog.log 2>&1 || true",
    "sudo dmesg > /var/log/datadog_weblog/dmesg.log 2>&1 || true",
    (
        "sudo systemctl list-dependencies docker.service > "
        "/var/log/datadog_weblog/docker_list_dependencies.log 2>&1 || true"
    ),
    "sudo systemctl list-timers --all > /var/log/datadog_weblog/system.timers.log 2>&1 || true",
    "sudo crontab -l > /var/log/datadog_weblog/crontab.log 2>&1 || true",
    "sudo cat /var/log/apt/history.log > /var/log/datadog_weblog/apt.log 2>&1 || true",
    "sudo cat /var/log/yum.log > /var/log/datadog_weblog/yum.log 2>&1 || true",
]


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

        _run_log_collection_commands(connection, vm)

        sftp = connection.open_sftp()
        for remote_folder_path in remote_folder_paths:
            local_folder_path = f"{local_base_logs_folder}/{remote_folder_path}"
            logger.info("Downloading: %s -> %s", remote_folder_path, local_folder_path)

            Path(local_folder_path).mkdir(parents=True, exist_ok=True)
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


def _run_log_collection_commands(connection: SSHClient, vm: _VirtualMachine) -> None:
    """Execute the remote log-collection commands, tolerating individual failures."""
    for cmd in _LOG_COLLECTION_COMMANDS:
        try:
            logger.info("Executing remote command: %s", cmd)
            _stdin, stdout, _stderr = connection.exec_command(cmd)
            exit_status = stdout.channel.recv_exit_status()
            logger.info("Remote command exit status: %s", exit_status)
        except Exception as exec_err:
            logger.warning("Failed executing command on %s: %s", vm.ssh_config.hostname, cmd)
            logger.exception(exec_err)


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
