import logging
import sys

from _pytest.terminal import TerminalReporter


DEBUG_LEVEL_STDOUT = 100


def get_log_formatter() -> logging.Formatter:
    return logging.Formatter("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%H:%M:%S")


class Logger(logging.Logger):
    terminal: TerminalReporter

    def stdout(self, message: str, *args) -> None:  # noqa: ANN002
        if self.isEnabledFor(DEBUG_LEVEL_STDOUT):
            # Yes, logger takes its '*args' as 'args'.
            self._log(DEBUG_LEVEL_STDOUT, message, args)  # pylint: disable=protected-access

            if hasattr(self, "terminal"):
                self.terminal.write_line(message)
                self.terminal.flush()
            else:
                # at this point, the logger may not yet be configured with the pytest terminal
                # so directly print in stdout
                print(message)  # noqa: T201

    def log_file_to_stdout(self, logfile: str, lines: list[str], tail_limit: int = 50) -> None:
        """When some important informations is stored inside a log file, it can be very handy to also print it
        in stdout. This function does not print in inside test.logs, as the data already exists in another log file
        """

        SEP = "=" * 30  # noqa: N806

        # if the logger is not yet be configured with the pytest terminal, directly use print in stdout
        print_method = self.terminal.write_line if hasattr(self, "terminal") else print

        print_method(f"\n{SEP} {logfile} last {tail_limit} lines {SEP}")
        print_method("")
        # print last <tail> lines in stdout
        print_method("".join(lines[-tail_limit:]))
        print_method("")

        if hasattr(self, "terminal"):
            self.terminal.flush()


logging.setLoggerClass(Logger)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.addLevelName(DEBUG_LEVEL_STDOUT, "STDOUT")


def get_logger(name: str = "tests", *, use_stdout: bool = False) -> Logger:
    result: Logger = logging.getLogger(name)  # type: ignore[assignment]

    if use_stdout:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.setFormatter(get_log_formatter())
        result.addHandler(stdout_handler)

    result.setLevel(logging.DEBUG)

    return result


logger = get_logger()
