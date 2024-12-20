import subprocess, datetime, os, time, signal, shlex
from utils.tools import logger
from utils import context
from retry import retry


def execute_command(command, timeout=None, logfile=None, subprocess_env=None, quiet=False):
    """Call shell-command and either return its output or kill it
    if it doesn't normally exit within timeout seconds and return None
    """
    applied_timeout = 90
    if timeout is not None:
        applied_timeout = timeout

    logger.debug(f"Launching Command: {_clean_secrets(command)} ")
    command_out_redirect = subprocess.PIPE
    if logfile:
        command_out_redirect = open(logfile, "w")

    if not subprocess_env:
        subprocess_env = os.environ.copy()

    output = ""
    try:
        start = datetime.datetime.now()
        process = subprocess.Popen(
            shlex.split(command), stdout=command_out_redirect, stderr=command_out_redirect, env=subprocess_env
        )

        while process.poll() is None:
            time.sleep(0.1)
            now = datetime.datetime.now()
            if (now - start).seconds > applied_timeout:
                os.kill(process.pid, signal.SIGKILL)
                os.waitpid(-1, os.WNOHANG)
                if timeout is None:
                    # If when we call this method we don't specify a timeout, we return None
                    return None
                else:
                    # if we specify a timeout, we raise an exception
                    raise Exception(f"Command: {_clean_secrets(command)} timed out after {applied_timeout} seconds")
        if not logfile:
            output = process.stdout.read()
            output = str(output, "utf-8")
            if not quiet:
                logger.debug(f"Command: {_clean_secrets(command)} \n {_clean_secrets(output)}")
            else:
                logger.info(f"Command: {_clean_secrets(command)}")
            if process.returncode != 0:
                output_error = process.stderr.read()
                logger.debug(f"Command: {_clean_secrets(command)} \n {_clean_secrets(output_error)}")
                raise Exception(f"Error executing command: {_clean_secrets(command)} \n {_clean_secrets(output)}")

    except Exception as ex:
        logger.error(f"Error executing command: {_clean_secrets(command)} \n {ex}")
        raise ex

    return output


def _clean_secrets(data_to_clean):
    """Clean secrets from the output."""
    if (
        hasattr(context.scenario, "api_key")
        and context.scenario.api_key
        and hasattr(context.scenario, "app_key")
        and context.scenario.app_key
    ):
        data_to_clean = data_to_clean.replace(context.scenario.api_key, "DD_API_KEY").replace(
            context.scenario.app_key, "DD_APP_KEY"
        )
    return data_to_clean


@retry(delay=1, tries=5)
def helm_add_repo(name, url, k8s_cluster_info, update=False):
    logger.info(f"Adding helm repo {name} with url {url} for cluster {k8s_cluster_info.cluster_name}")
    execute_command(f"helm repo add {name} {url}")
    if update:
        execute_command(f"helm repo update")


@retry(delay=1, tries=5)
def helm_install_chart(k8s_cluster_info, name, chart, set_dict={}, value_file=None, upgrade=False):
    # Copy and replace cluster name in the value file
    custom_value_file = None
    if value_file:
        with open(value_file) as file:
            value_data = file.read()

        value_data = value_data.replace("$$CLUSTER_NAME$$", str(k8s_cluster_info.cluster_name))

        custom_value_file = f"{context.scenario.host_log_folder}/{k8s_cluster_info.cluster_name}_help_values.yaml"

        with open(custom_value_file, "w") as fp:
            fp.write(value_data)
            fp.seek(0)

    set_str = ""
    if set_dict:
        for key, value in set_dict.items():
            set_str += f" --set {key}={value}"

    command = f"helm install {name} --debug --wait {set_str} {chart}"
    if upgrade:
        command = f"helm upgrade {name} --debug --install --wait {set_str} {chart}"
    if custom_value_file:
        command = f"helm install {name} {set_str} --debug -f {custom_value_file} {chart}"
        if upgrade:
            command = f"helm upgrade {name} {set_str} --debug --install -f {custom_value_file} {chart}"
    execute_command("kubectl config current-context")
    execute_command(command, timeout=90, quiet=True)  # Too many traces to show in the logs
