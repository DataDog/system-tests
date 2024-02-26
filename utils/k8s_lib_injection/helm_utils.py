import os
from utils.tools import logger

import subprocess


def execute_command(command, timeout=30):
    """call shell-command and either return its output or kill it
  if it doesn't normally exit within timeout seconds and return None"""
    import subprocess, datetime, os, time, signal

    start = datetime.datetime.now()
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while process.poll() is None:
        time.sleep(0.1)
        now = datetime.datetime.now()
        if (now - start).seconds > timeout:
            os.kill(process.pid, signal.SIGKILL)
            os.waitpid(-1, os.WNOHANG)
            return None
    output = process.stdout.read()
    logger.debug(f"Command: {command} \n {output}")
    return output


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
        command = f"helm install {name} --wait {set_str} -f {value_file} {chart}"

    execute_command(command)
