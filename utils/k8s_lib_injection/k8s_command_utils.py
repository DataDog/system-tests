import subprocess, datetime, os, time, signal
from utils.tools import logger


def execute_command(command, timeout=None):
    """call shell-command and either return its output or kill it
  if it doesn't normally exit within timeout seconds and return None"""
    applied_timeout = 90
    if timeout is not None:
        applied_timeout = timeout

    logger.debug(f"Launching Command: {command} ")
    output = ""
    try:
        start = datetime.datetime.now()
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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
                    raise Exception(f"Command: {command} timed out after {applied_timeout} seconds")

        output = process.stdout.read()
        logger.debug(f"Command: {command} \n {output}")
        if process.returncode != 0:
            output_error = process.stderr.read()
            logger.debug(f"Command: {command} \n {output_error}")
            raise Exception(f"Error executing command: {command} \n {output}")

    except Exception as ex:
        logger.error(f"Error executing command: {command} \n {ex}")
        raise ex

    return output


def ensure_cluster():
    execute_command(
        "kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1 --name lib-injection-testing --config utils/k8s_lib_injection/resources/kind-config.yaml"
    )
    execute_command("kubectl wait --for=condition=Ready nodes --all --timeout=5m")


def destroy_cluster():
    execute_command("kind delete cluster --name lib-injection-testing")
    execute_command("docker rm -f lib-injection-testing-control-plane")


def helm_add_repo(name, url, update=False):

    execute_command(f"helm repo add {name} {url}")
    if update:
        execute_command(f"helm repo update")


def helm_install_chart(name, chart, set_dict={}, value_file=None):
    set_str = ""
    if set_dict:
        for key, value in set_dict.items():
            set_str += f" --set {key}={value}"

    command = f"helm install {name} --wait {set_str} {chart}"
    if value_file:
        # command = f"helm install {name} --wait {set_str} -f {value_file} {chart}"
        command = f"helm install {name} {set_str} -f {value_file} {chart}"

    execute_command(command, timeout=90)
