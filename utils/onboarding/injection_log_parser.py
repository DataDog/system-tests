import json

from utils.tools import logger


def command_injection_skipped(command_line, log_local_path):
    """ From parsed log, search on the list of logged commands if one command has been skipped from the instrumentation"""
    command, command_args = _parse_command(command_line)
    logger.debug(f"- Checking command: {command_args}")
    for command_desc in _get_commands_from_log_file(log_local_path):
        # First line contains the name of the intercepted command
        first_line_json = json.loads(command_desc[0])
        if command in first_line_json["inFilename"]:
            # last line contains the skip message. The command was skipped by build-in deny list or by user deny list
            last_line_json = json.loads(command_desc[-1])
            if last_line_json["msg"] == "not injecting; on deny list":
                logger.debug(f"    Command {command_args} was skipped by build-in deny list")
                return True
            elif last_line_json["msg"] == "not injecting; on user deny list":
                logger.debug(f"    Command {command_args} was skipped by user defined deny process list")
                return True

            # Perhaps the command was instrumented or could be skipped by its arguments. Checking
            elif _get_command_props_values(command_desc, command_args) is True:
                if last_line_json["msg"] == "error when parsing" and last_line_json["error"].startswith(
                    "skipping due to ignore rules for language"
                ):
                    logger.info(f"    Command {command_args} was skipped by ignore arguments")
                    return True

                logger.info(f"    command {command_args} is found but it was instrumented!")
                return False
    logger.info(f"    Command {command} was NOT FOUND")
    raise ValueError(f"Command {command} was NOT FOUND")


def _parse_command(command):
    command_args = command.split()
    command = None
    # Remove SUDO -E option
    if "sudo" in command_args:
        command_args.remove("sudo")
    if "-E" in command_args:
        command_args.remove("-E")

    # Command could not be the first arg example "env_var=1 ./mycommand"
    for com in list(command_args):
        if "=" in com:
            command_args.remove(com)
            continue
        return com, command_args


def _get_command_props_values(command_instrumentation_desc, command_args_check):
    """ Search into command_instrumentation_desc (lines related with the command on the log file) if the command and arguments are equal 
        The line that contains the command with args should be like this (example for java -help):
            {"level":"debug","ts":1,"caller":"xx","msg":"props values","props":{"Env":"","Service":"","Version":"","ProcessProps":
            {"Path":"/usr/bin/java","Args":["java","-help"]},"ContainerProps":{"Labels":null,"Name":"","ShortName":"","Tag":""}}}
    """
    for line in command_instrumentation_desc:
        if "props values" in line:
            line_json = json.loads(line)
            command_log_args = line_json["props"]["ProcessProps"]["Args"]
            command_compared_result = set(command_log_args) & set(command_args_check)
            is_same_command = len(command_log_args) == len(command_args_check) and len(command_compared_result) == len(
                command_args_check
            )

            return is_same_command
    return False


def _get_commands_from_log_file(log_local_path):
    """ From instrumentation log file, extract all commands parsed by dd-injection (the log level should be DEBUG)  """

    store_as_command = False
    command_lines = []
    with open(log_local_path) as f:
        for line in f:
            if "starting process" in line:
                store_as_command = True
                continue
            if "exiting process" in line:
                store_as_command = False
                yield command_lines.copy()
                command_lines = []
                continue

            if store_as_command:
                command_lines.append(line)


def main():
    log_file = "logs_onboarding_host_block_list/host_injection_21711f84-86b3-4125-9a5f-cd129195d99a.log"
    command = "java -Dversion=-version -jar myapp.jar"
    skipped = command_injection_skipped(command, log_file)
    logger.info(f"The command was skiped? {skipped}")


if __name__ == "__main__":
    main()
