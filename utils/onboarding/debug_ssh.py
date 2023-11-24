import os
import paramiko
from utils.tools import logger


def debug_info_ssh(ip, user, pem_file, log_folder):

    try:
        logger.info(f"Extracting debug information from machine {ip}")
        cert = paramiko.RSAKey.from_private_key_file(pem_file)
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        logger.info(f"Connecting [{ip}]")
        c.connect(hostname=ip, username=user, pkey=cert)
        logger.info(f"Connected [{ip}]")

        # Create folder for this mnachine logs files
        vm_debug_log_folder = f"{log_folder}/{ip}_debug"
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
    with open(file_to_write, "w") as stdout_file:
        stdout_file.writelines(stdout.readlines())


def _print_running_processes(sshClient, file_to_write):
    """ Processes running on the machine """
    _, stdout, _ = sshClient.exec_command("ps -fea")
    with open(file_to_write, "w") as stdout_file:
        stdout_file.writelines(stdout.readlines())


def _print_directories_permissions(sshClient, file_to_write):
    """ List datadog directories permission """
    permissions_command = """for dir in ` sudo find / -name "*datadog*" -type d -maxdepth 3`; do
                echo ".:: ***************** FOLDER: $dir ******************::."
                sudo ls -la $dir
            done"""
    _, stdout, _ = sshClient.exec_command(permissions_command)
    with open(file_to_write, "w") as stdout_file:
        stdout_file.writelines(stdout.readlines())


def _print_agent_install(sshClient, file_to_write):
    """Cat agent installation script"""
    _, stdout, _ = sshClient.exec_command("cat $(pwd)/ddagent-install.log")
    with open(file_to_write, "w") as stdout_file:
        stdout_file.writelines(stdout.readlines())


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
    with open(file_to_write, "w") as stdout_file:
        stdout_file.writelines(stdout.readlines())


def _print_app_tracer_host_logs(sshClient, file_to_write):
    """App tracer logs"""
    _, stdout, _ = sshClient.exec_command("sudo systemctl status test-app.service")
    with open(file_to_write, "w") as stdout_file:
        stdout_file.writelines(stdout.readlines())


def _print_app_tracer_container_logs(sshClient, file_to_write):
    """App container logs"""
    _, stdout, _ = sshClient.exec_command("sudo docker-compose logs")
    with open(file_to_write, "w") as stdout_file:
        stdout_file.writelines(stdout.readlines())


def _print_agent_container_logs(sshClient, file_to_write):
    """Agent container logs"""
    _, stdout, _ = sshClient.exec_command("sudo docker-compose -f docker-compose-agent-prod.yml logs datadog")
    with open(file_to_write, "w") as stdout_file:
        stdout_file.writelines(stdout.readlines())
