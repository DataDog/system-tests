import json
from pathlib import Path

from utils._logger import logger


def exclude_telemetry_logs_filter(line):
    return '"command":"telemetry"' not in line and '"caller":"telemetry/' not in line


def command_injection_skipped(command_line, log_local_path):
    """From parsed log, search on the list of logged commands
    if one command has been skipped from the instrumentation
    """
    command, command_args = _parse_command(command_line)
    logger.debug(f"- Checking command: {command_args}")
    for command_desc in _get_commands_from_log_file(log_local_path, exclude_telemetry_logs_filter):
        # First line contains the name of the intercepted command
        first_line_json = json.loads(command_desc[0])
        if command in first_line_json["inFilename"]:
            # last line contains the skip message. The command was skipped by build-in deny list or by user deny list
            last_line_json = json.loads(command_desc[-1])
            # pylint: disable=R1705
            if last_line_json["msg"] == "not injecting; on deny list":
                logger.debug(f"    Command {command_args} was skipped by build-in deny list")
                return True
            elif last_line_json["msg"] == "not injecting; on user deny list":
                logger.debug(f"    Command {command_args} was skipped by user defined deny process list")
                return True
            elif last_line_json["msg"] in ["error injecting", "error when parsing", "skipping"] and (
                last_line_json["error"].startswith(
                    (
                        "skipping due to ignore rules for language",
                        "error when parsing: skipping due to ignore rules for language",
                    )
                )
            ):
                logger.info(f"    Command {command_args} was skipped by ignore arguments")
                return True
            logger.info(f"    Missing injection deny: {last_line_json}")
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
        return Path(com).name, command_args

    return None, None


def _get_commands_from_log_file(log_local_path, line_filter):
    """From instrumentation log file, extract all commands parsed by dd-injection (the log level should be DEBUG)"""

    store_as_command = False
    command_lines = []
    with open(log_local_path, encoding="utf-8") as f:
        for line in f:
            if not line_filter(line):
                continue
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
