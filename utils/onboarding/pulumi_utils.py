import os
import logging
import logging.config
import shutil
import pulumi
from pulumi import Output
import pulumi_command as command
from utils.tools import logger


def remote_docker_login(command_id, user, password, connection, depends_on):
    # Workaround: Sometimes I get "docker" command not found. Wait some seconds?
    command_exec = f"sleep 5 && sudo docker login --username={user} --password={password} || true"
    cmd_exec_install = command.remote.Command(
        command_id, connection=connection, create=command_exec, opts=pulumi.ResourceOptions(depends_on=[depends_on]),
    )
    return cmd_exec_install


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
    output_callback=None,
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

            logger.info(f"RMM REMOTEPATH TIENE VALOR INICIAL: {remote_path}")
            if os.path.isfile(file_to_copy["local_path"]):
                logger.info("RMM COPIANDO FICHERO.....")
                # Launch copy file command
                cmd_cp_webapp = command.remote.CopyFile(
                    file_to_copy["name"] + "-" + command_identifier,
                    connection=connection,
                    local_path=file_to_copy["local_path"],
                    remote_path=remote_path,
                    opts=pulumi.ResourceOptions(depends_on=[depends_on]),
                )
                depends_on = cmd_cp_webapp
            else:
                logger.info("RMM COPIANDO DIRECTORIO .....")
                depends_on = remote_copy_folders(
                    file_to_copy["local_path"], remote_path, command_identifier, connection, depends_on
                )

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
    if output_callback:
        cmd_exec_install.stdout.apply(output_callback)

    return cmd_exec_install


def remote_copy_folders(source_folder, destination_folder, command_id, connection, depends_on):
    copy_depends_on = depends_on
    for file_name in os.listdir(source_folder):
        # construct full file path
        source = source_folder + "/" + file_name
        destination = destination_folder + "/" + file_name
        destination = os.path.basename(destination)
        logger.debug(f"remote_copy_folders: source:[{source}] and remote destination: [{destination}] ")
        if os.path.isfile(source):
            # Launch copy file command
            cmd_cp = command.remote.CopyFile(
                file_name + "-" + command_id,
                connection=connection,
                local_path=source,
                remote_path=destination,
                opts=pulumi.ResourceOptions(depends_on=[copy_depends_on]),
            )
            copy_depends_on = cmd_cp
        else:
            copy_depends_on = remote_copy_folders(source, destination, command_id, connection, depends_on)
    return copy_depends_on


def pulumi_logger(scenario_name, log_name, level=logging.INFO):
    formatter = logging.Formatter("%(message)s")
    handler = logging.FileHandler(f"logs_{scenario_name}/{log_name}.log")
    handler.setFormatter(formatter)
    specified_logger = logging.getLogger(log_name)
    specified_logger.setLevel(level)
    specified_logger.addHandler(handler)
    return specified_logger
