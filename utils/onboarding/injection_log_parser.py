import re
from collections.abc import Callable
from pathlib import Path

from utils._logger import logger

WLS_DENIED_INJECTION = "Workload selection denied injection"
WLS_ALLOWED_INJECTION = "Workload selection allowed injection: continuing"
NO_KNOWN_RUNTIME = "No known runtime was detected - not injecting!"


def exclude_telemetry_logs_filter(line: str):
    return '"command":"telemetry"' not in line and '"caller":"telemetry/' not in line


def command_injection_skipped(command_line: str, log_local_path: str):
    """Determine if the given command was skipped from auto injection
    (e.g. by workload selection policies or no language matched).
    """
    command, _ = _parse_command(command_line)
    logger.debug(f"- Checking command: {command_line}")
    for process_logs in _get_process_logs_from_log_file(log_local_path, exclude_telemetry_logs_filter):
        process_exe = _get_exe_from_log_line(process_logs[0])
        if process_exe is None or command != process_exe:
            continue
        if _process_chunk_means_skipped(process_logs):
            logger.debug(f"    Command '{command}' was skipped (denied by WLS or no known runtime)")
            return True
        logger.info(f"    Command '{command}' was allowed and injected")
        return False

    logger.info(f"    Command {command} was NOT FOUND")
    raise ValueError(f"Command {command} was NOT FOUND")


def _process_chunk_means_skipped(chunk: list[str]) -> bool:
    """True if injection was skipped: denied by workload selection or no known runtime detected."""
    text = "\n".join(chunk)
    return WLS_DENIED_INJECTION in text or NO_KNOWN_RUNTIME in text


def _get_exe_from_log_line(line: str) -> str | None:
    """Extract executable name from the log line "process_exe: 'X'"."""
    match = re.search(r"process_exe:\s*['\"]([^'\"]+)['\"]", line)
    if match:
        return Path(match.group(1)).name
    return None


def _parse_command(command: str):
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


def _get_process_logs_from_log_file(log_local_path: str, line_filter: Callable):
    r"""From instrumentation log file, extract all log lines per process.

    A process chunk starts at the line containing \"process_exe:\" and runs until
    \"injector finished\" (or the next \"process_exe:\"). This includes WLS decision
    lines and post-WLS lines like \"No known runtime was detected - not injecting!\".
    """
    process_logs = []
    with open(log_local_path, encoding="utf-8") as f:
        for line in f:
            if not line_filter(line):
                continue
            if "process_exe:" in line:
                if process_logs:
                    yield process_logs.copy()
                process_logs = [line]
                continue
            if process_logs and WLS_DENIED_INJECTION in line:
                process_logs.append(line)
                yield process_logs.copy()
                process_logs = []
                continue
            if "injector finished" in line:
                process_logs.append(line)
                yield process_logs.copy()
                process_logs = []
                continue


def main():
    log_file = "logs_onboarding_host_block_list/host_injection_21711f84-86b3-4125-9a5f-cd129195d99a.log"
    command = "java -Dversion=-version -jar myapp.jar"
    skipped = command_injection_skipped(command, log_file)
    logger.info(f"The command was skipped? {skipped}")


if __name__ == "__main__":
    main()
