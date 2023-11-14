import os
import logging
import logging.config
import pathlib
import uuid

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
    docker_user=None,
    docker_pass=None,
):
    # List to store the latest commands in order to manage dependecy between commands
    # (wait for one command finished before launch next command)
    quee_depends_on = [depends_on]

    # Do we need to add env variables?
    if install_info is None:
        return depends_on

    # DD API KEYS IN THE COMMAND
    if add_dd_keys:
        command_exec = "DD_API_KEY=" + dd_api_key + " DD_SITE=" + dd_site + " " + install_info["command"]
    else:
        command_exec = install_info["command"]

    # Docker login if we need (avoid too many request on CI)
    if docker_user is not None:
        command_exec = f"sudo docker login --username={docker_user} --password={docker_pass} || true && {command_exec}"

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
            opts=pulumi.ResourceOptions(depends_on=[quee_depends_on.pop()]),
        )
        webapp_build.stdout.apply(lambda outputlog: pulumi_logger(scenario_name, "build_local_weblogs").info(outputlog))
        quee_depends_on.insert(0, webapp_build)

    # Copy files from local to remote if we need
    if "copy_files" in install_info:
        for file_to_copy in install_info["copy_files"]:

            # If we don't use remote_path, the remote_path will be a default remote user home
            if "remote_path" in file_to_copy:
                remote_path = file_to_copy["remote_path"]
            else:
                remote_path = os.path.basename(file_to_copy["local_path"])

            if os.path.isfile(file_to_copy["local_path"]):
                logger.debug(f"Copy file from {file_to_copy['local_path']} to {remote_path}")
                # Launch copy file command
                quee_depends_on.insert(
                    0,
                    command.remote.CopyFile(
                        file_to_copy["name"] + "-" + command_identifier,
                        connection=connection,
                        local_path=file_to_copy["local_path"],
                        remote_path=remote_path,
                        opts=pulumi.ResourceOptions(depends_on=[quee_depends_on.pop()]),
                    ),
                )

            else:
                quee_depends_on.insert(
                    0,
                    remote_copy_folders(
                        file_to_copy["local_path"], remote_path, command_identifier, connection, quee_depends_on.pop()
                    ),
                )

    # Execute a basic command on our server.
    cmd_exec_install = command.remote.Command(
        command_identifier,
        connection=connection,
        create=command_exec,
        opts=pulumi.ResourceOptions(
            depends_on=[quee_depends_on.pop()]
        ),  # Here the quee should contain only one element
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


def remote_copy_folders(source_folder, destination_folder, command_id, connection, depends_on, relative_path=False):
    quee_depends_on = [depends_on]
    for file_name in os.listdir(source_folder):
        # construct full file path
        source = source_folder + "/" + file_name
        destination = destination_folder + "/" + file_name
        logger.debug(f"remote_copy_folders: source:[{source}] and remote destination: [{destination}] ")

        if os.path.isfile(source):
            if not relative_path:
                destination = os.path.basename(destination)

            logger.debug(f"Copy single file: source:[{source}] and remote destination: [{destination}] ")
            # Launch copy file command
            quee_depends_on.insert(
                0,
                command.remote.CopyFile(
                    source + "-" + command_id,
                    connection=connection,
                    local_path=source,
                    remote_path=destination,
                    opts=pulumi.ResourceOptions(depends_on=[quee_depends_on.pop()]),
                ),
            )
        else:
            # mkdir remote
            if not relative_path:
                p = pathlib.Path("/" + destination)
                destination = str(p.relative_to(*p.parts[:2]))
            logger.debug(f"Creating remote folder: {destination}")

            quee_depends_on.insert(
                0,
                command.remote.Command(
                    "mkdir-" + destination + "-" + str(uuid.uuid4()) + "-" + command_id,
                    connection=connection,
                    create=f"mkdir -p {destination}",
                    opts=pulumi.ResourceOptions(depends_on=[quee_depends_on.pop()]),
                ),
            )
            quee_depends_on.insert(
                0,
                remote_copy_folders(
                    source, destination, command_id, connection, quee_depends_on.pop(), relative_path=True
                ),
            )
    return quee_depends_on.pop()  # Here the quee should contain only one element


def pulumi_logger(scenario_name, log_name, level=logging.INFO):
    formatter = logging.Formatter("%(message)s")
    handler = logging.FileHandler(f"logs_{scenario_name}/{log_name}.log")
    handler.setFormatter(formatter)
    specified_logger = logging.getLogger(log_name)
    specified_logger.setLevel(level)
    specified_logger.addHandler(handler)
    return specified_logger
