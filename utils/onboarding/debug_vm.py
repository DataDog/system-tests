import os
from pathlib import Path
import paramiko
from utils._logger import logger


def extract_logs_to_file(logs_data, log_folder):
    """Extract logs to different files.
    The logs_data is a string results of executing the command:
     find /var/log -type f -name "*.log"| xargs tail -n +1
    """

    output_file = None
    for line in logs_data.splitlines():
        if "==>" in line and "<==" in line:
            filename = line.split("==>")[1].split("<==")[0]
            logger.info(f"Copy log data from [{filename.strip()}]")
            output_file = Path(log_folder + filename.strip())
            output_file.parent.mkdir(exist_ok=True, parents=True)
        elif output_file is not None:
            with open(output_file, "a", encoding="utf-8") as out:
                out.write(f"{line}\n")


def debug_info_ssh(vm_name, ip, user, pem_file, log_folder):
    """Using SSH connects to VM and extract VM status information"""

    try:
        logger.info(f"Extracting debug information from machine {ip}")
        cert = paramiko.RSAKey.from_private_key_file(pem_file)
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        logger.info(f"Connecting [{ip}]")
        c.connect(hostname=ip, username=user, pkey=cert)
        logger.info(f"Connected [{ip}]")

        # Create folder for this mnachine logs files
        vm_debug_log_folder = f"{log_folder}/{vm_name}_debug"
        os.mkdir(vm_debug_log_folder)
        vm_debug_file_prefix = f"{vm_debug_log_folder}/{ip}_"

        _print_env_variables(c, f"{vm_debug_file_prefix}_env.log")
        _print_running_processes(c, f"{vm_debug_file_prefix}_processes.log")
        _print_directories_permissions(c, f"{vm_debug_file_prefix}_directories.log")
        _print_agent_install(c, f"{vm_debug_file_prefix}_ddagent-install.log")
        _print_agent_host_logs(c, f"{vm_debug_file_prefix}_ddagent-host-logs.log")
        _print_app_tracer_host_logs(c, f"{vm_debug_file_prefix}_app-tracer-host-logs.log")
        _print_app_tracer_container_logs(c, f"{vm_debug_file_prefix}_app-tracer-container-logs.log")
        _print_agent_container_logs(c, f"{vm_debug_file_prefix}_ddagent-container-logs.log")

    except Exception as e:  #
        logger.error(f"Cannot connect to remote machnine {ip}")
        logger.exception(e)


def _print_env_variables(sshClient, file_to_write):
    """Echo VM env"""
    _, stdout, _ = sshClient.exec_command("env")
    _write_to_debug_file(stdout, file_to_write)


def _print_running_processes(sshClient, file_to_write):
    """Processes running on the machine"""
    _, stdout, _ = sshClient.exec_command("ps -fea")
    _write_to_debug_file(stdout, file_to_write)


def _print_directories_permissions(sshClient, file_to_write):
    """List datadog directories permission"""
    permissions_command = """for dir in ` sudo find / -name "*datadog*" -type d -maxdepth 3`; do
                echo ".:: Folder: $dir ::."
                sudo ls -la $dir
            done
            echo ".:: Folder: /opt/datadog/apm/inject/ ::."
            sudo ls -la /opt/datadog/apm/inject/
            echo ".:: Folder: /opt/datadog/apm/inject/run/ ::."
            sudo ls -la /opt/datadog/apm/inject/run/
            echo ".:: Folder /etc/datadog-agent/inject/ ::."
            sudo ls -la /etc/datadog-agent/inject/
            """
    _, stdout, _ = sshClient.exec_command(permissions_command)
    _write_to_debug_file(stdout, file_to_write)


def _print_agent_install(sshClient, file_to_write):
    """Cat agent installation script"""
    _, stdout, _ = sshClient.exec_command("cat $(pwd)/ddagent-install.log")
    _write_to_debug_file(stdout, file_to_write)


def _print_agent_host_logs(sshClient, file_to_write):
    """Agent logs"""

    command = """
                  echo ".:: ************ /var/log/datadog/agent.log ************* ::."
                  sudo cat /var/log/datadog/agent.log
                  echo ".:: ************ /var/log/datadog/process-agent.log ************* ::."
                  sudo cat /var/log/datadog/process-agent.log
                  echo ".:: ************ /var/log/datadog/trace-agent.log ************* ::."
                  sudo cat /var/log/datadog/trace-agent.log
                    """
    _, stdout, _ = sshClient.exec_command(command)
    _write_to_debug_file(stdout, file_to_write)


def _print_app_tracer_host_logs(sshClient, file_to_write):
    """App tracer logs"""
    _, stdout, _ = sshClient.exec_command("sudo systemctl status test-app.service")
    _write_to_debug_file(stdout, file_to_write)

    _print_app_tracer_host_dotnet_logs(sshClient, file_to_write)


def _print_app_tracer_host_dotnet_logs(sshClient, file_to_write):
    """App tracer logs for dotnet (dotnet tracer doesn't write debug tracer in stdout)"""
    path = Path(file_to_write)
    root = path.parent / path.stem
    file_to_write_dotnet = f"{root}_dotnet.log"
    _, stdout_dotnet, _ = sshClient.exec_command("sudo find /var/log/datadog/dotnet/ -type f | xargs tail -n +1")
    _write_to_debug_file(stdout_dotnet, file_to_write_dotnet)


def _print_app_tracer_container_logs(sshClient, file_to_write):
    """App container logs"""
    _, stdout, _ = sshClient.exec_command("sudo docker-compose logs")
    _write_to_debug_file(stdout, file_to_write)


def _print_agent_container_logs(sshClient, file_to_write):
    """Agent container logs"""
    _, stdout, _ = sshClient.exec_command("sudo docker-compose -f docker-compose-agent-prod.yml logs datadog")
    _write_to_debug_file(stdout, file_to_write)


def _write_to_debug_file(stdout, file_to_write):
    full_output = stdout.readlines()
    if full_output:
        with open(file_to_write, mode="w", encoding="utf-8") as stdout_file:
            stdout_file.writelines(full_output)
