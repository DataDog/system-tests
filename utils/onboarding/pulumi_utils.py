import os
from utils.tools import logger
import pulumi
import pulumi_aws as aws
import pulumi_command as command
from pulumi import Output

import logging
import logging.config


def remote_install(
    connection,
    command_identifier,
    install_info,
    depends_on,
    add_dd_keys=False,
    logger_name=None,
    dd_api_key=None,
    dd_site=None,
    scenario_name=None,
):
    # Do we need to add env variables?
    if install_info is None:
        return depends_on
    if add_dd_keys:
        command_exec = "DD_API_KEY=" + dd_api_key + " DD_SITE=" + dd_site + " " + install_info["command"]
    else:
        command_exec = install_info["command"]

    local_command = None
    # Execute local command if we need
    if "local-command" in install_info:
        local_command = install_info["local-command"]

    # Execute local script if we need
    if "local-script" in install_info:
        local_command = "sh " + install_info["local-script"]

    if local_command:
        webapp_build = command.local.Command(
            "local-script_" + command_identifier,
            create=local_command,
            opts=pulumi.ResourceOptions(depends_on=[depends_on]),
        )
        webapp_build.stdout.apply(lambda outputlog: pulumi_logger(scenario_name, "build_local_weblogs").info(outputlog))
        depends_on = webapp_build

    # Copy files from local to remote if we need
    if "copy_files" in install_info:
        for file_to_copy in install_info["copy_files"]:

            # If we don't use remote_path, the remote_path will be a default remote user home
            if "remote_path" in file_to_copy:
                remote_path = file_to_copy["remote_path"]
            else:
                remote_path = os.path.basename(file_to_copy["local_path"])

            # Launch copy file command
            cmd_cp_webapp = command.remote.CopyFile(
                file_to_copy["name"] + "-" + command_identifier,
                connection=connection,
                local_path=file_to_copy["local_path"],
                remote_path=remote_path,
                opts=pulumi.ResourceOptions(depends_on=[depends_on]),
            )
        depends_on = cmd_cp_webapp

    # Execute a basic command on our server.
    cmd_exec_install = command.remote.Command(
        command_identifier,
        connection=connection,
        create=command_exec,
        opts=pulumi.ResourceOptions(depends_on=[depends_on]),
    )
    if logger_name:
        cmd_exec_install.stdout.apply(lambda outputlog: pulumi_logger(scenario_name, logger_name).info(outputlog))
    else:
        # If there isn't logger name specified, we will use the host/ip name to store all the logs of the
        # same remote machine in the same log file
        Output.all(connection.host, cmd_exec_install.stdout).apply(
            lambda args: pulumi_logger(scenario_name, args[0]).info(args[1])
        )

    return cmd_exec_install


def pulumi_logger(scenario_name, log_name, level=logging.INFO):
    formatter = logging.Formatter("%(message)s")
    handler = logging.FileHandler(f"logs_{scenario_name}/{log_name}.log")
    handler.setFormatter(formatter)
    specified_logger = logging.getLogger(log_name)
    specified_logger.setLevel(level)
    specified_logger.addHandler(handler)
    return specified_logger
