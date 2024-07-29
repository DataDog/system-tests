# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Check data that are sent to logs file on weblog"""

import json
import re
import os

from utils._context.core import context
from utils.tools import logger
from utils.interfaces._core import InterfaceValidator


class _LogsInterfaceValidator(InterfaceValidator):
    def __init__(self, name, new_log_line_pattern=None):
        super().__init__(name)

        self._skipped_patterns = [
            re.compile(r"^\s*$"),
        ]
        self._new_log_line_pattern = re.compile(new_log_line_pattern or ".")
        self._parsers = []
        self.timeout = 0
        self._data_list = []

    def _get_files(self):
        raise NotImplementedError()

    def _clean_line(self, line):
        return line

    def _is_new_log_line(self, line):
        return self._new_log_line_pattern.search(line)

    def _is_skipped_line(self, line):
        for pattern in self._skipped_patterns:
            if pattern.search(line):
                return True

        return False

    def _get_standardized_level(self, level):
        return level

    def _read(self):
        for filename in self._get_files():
            logger.info(f"For {self}, reading {filename}")
            log_count = 0
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    buffer = []
                    for line in f:
                        if line.endswith("\n"):
                            line = line[:-1]  # remove tailing \n
                        line = self._clean_line(line)

                        if self._is_skipped_line(line):
                            continue

                        if self._is_new_log_line(line) and len(buffer) != 0:
                            log_count += 1
                            yield "\n".join(buffer) + "\n"
                            buffer = []

                        buffer.append(line)

                    log_count += 1
                    yield "\n".join(buffer) + "\n"

                logger.info(f"Reading {filename} is finished, {log_count} has been treated")
            except FileNotFoundError:
                logger.debug(f"File not found, skipping it: {filename}")

    def load_data(self):
        logger.debug(f"Load data for log interface {self.name}")

        for log_line in self._read():

            parsed = {}
            for parser in self._parsers:
                m = parser.match(log_line)
                if m:
                    parsed = m.groupdict()
                    if "level" in parsed:
                        parsed["level"] = self._get_standardized_level(parsed["level"])
                    break

            parsed["raw"] = log_line

            self._data_list.append(parsed)

    def get_data(self):
        yield from self._data_list

    def validate(self, validator, success_by_default=False):

        for data in self.get_data():
            try:
                if validator(data) is True:
                    return
            except Exception:
                logger.error(f"{data} did not validate this test")
                raise

        if not success_by_default:
            raise ValueError("Test has not been validated by any data")

    def assert_presence(self, pattern, **extra_conditions):
        validator = _LogPresence(pattern, **extra_conditions)
        self.validate(validator.check, success_by_default=False)

    def assert_absence(self, pattern, allowed_patterns=None):
        validator = _LogAbsence(pattern, allowed_patterns)
        self.validate(validator.check, success_by_default=True)


class _StdoutLogsInterfaceValidator(_LogsInterfaceValidator):
    def __init__(self, container_name, new_log_line_pattern=None):
        super().__init__(f"{container_name} stdout", new_log_line_pattern=new_log_line_pattern)
        self.container_name = container_name

    def _get_files(self):
        return [
            f"{context.scenario.host_log_folder}/docker/{self.container_name}/stdout.log",
            f"{context.scenario.host_log_folder}/docker/{self.container_name}/stderr.log",
        ]


class _LibraryStdout(_StdoutLogsInterfaceValidator):
    def __init__(self):
        super().__init__("weblog")
        self.library = None

    def init_patterns(self, library):
        self.library = library
        p = "(?P<{}>{})".format

        self._skipped_patterns += [
            re.compile(r"^Attaching to systemtests_weblog_1$"),
            re.compile(r"systemtests_weblog_1 exited with code \d+"),
        ]

        if library == "java":
            self._skipped_patterns += [
                re.compile(r"^[ /\\_,''.()=`|]*$"),  # Java Spring ASCII art
                re.compile(r"^ +:: Spring Boot :: +\(v\d+.\d+.\d+(-SNAPSHOT)?\)$"),
            ]
            self._new_log_line_pattern = re.compile(r"^(\[dd.trace )?\d{4}-\d\d-\d\d")

            source = p("source", r"[a-z\.]+")
            timestamp = p("timestamp", r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d:\d\d\d [+\-]0000")
            thread = p("thread", r"[^\]]+")
            level = p("level", r"\w+")
            klass = p("klass", r"[\w\.$]+")
            message = p("message", r".*")
            self._parsers.append(re.compile(rf"^\[{source} {timestamp}\] \[{thread}\] {level} {klass} - {message}"))

            timestamp = p("timestamp", r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d")
            klass = p("klass", r"[\w\.$\[\]/]+")
            self._parsers.append(re.compile(rf"^{timestamp} +{level} \d -+ \[ *{thread}\] +{klass} *: *{message}"))

        elif library == "dotnet":
            self._new_log_line_pattern = re.compile(r"^\s*(info|debug|error)")
        elif library == "php":
            self._skipped_patterns += [
                re.compile(r"^(?!\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\]\[[a-z]+\]\[\d+\])"),
            ]

            timestamp = p("timestamp", r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}")
            level = p("level", r"\w+")
            thread = p("thread", r"\d+")
            message = p("message", r".+")
            self._parsers.append(re.compile(rf"\[{timestamp}\]\[{level}\]\[{thread}\] {message}"))
        else:
            self._new_log_line_pattern = re.compile(r".")
            self._parsers.append(re.compile(p("message", r".*")))

    def _clean_line(self, line):
        if line.startswith("weblog_1         | "):
            line = line[19:]

        return line

    def _get_standardized_level(self, level):
        if self.library == "php":
            return level.upper()

        return super()._get_standardized_level(level)


class _LibraryDotnetManaged(_LogsInterfaceValidator):
    def __init__(self):
        super().__init__(".Net tracer-managed logs")

        self._skipped_patterns += [
            re.compile(
                r'\{ MachineName: "\.", Process: "\[1 dotnet\]", AppDomain: "\[1 app\]", TracerVersion: "[\d\.]*" }'
            )
        ]

        self._new_log_line_pattern = re.compile(r"^\d\d\d\d-\d\d-\d\d")

        p = "(?P<{}>{})".format
        timestamp = p("timestamp", r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d.\d\d\d [+\-]00:00")
        # thread = p("thread", r"[\w\-]+")
        level = p("level", r"\w+")
        message = p("message", r".*")
        self._parsers.append(re.compile(rf"^{timestamp} \[{level}\] {message}"))

    def _get_files(self):
        result = []

        try:
            files = os.listdir(f"{context.scenario.host_log_folder}/docker/weblog/logs/")
        except FileNotFoundError:
            files = []

        for f in files:
            filename = os.path.join(f"{context.scenario.host_log_folder}/docker/weblog/logs/", f)

            if os.path.isfile(filename) and re.search(r"dotnet-tracer-managed-dotnet-\d+(_\d+)?.log", filename):
                result.append(filename)

        return result

    def _get_standardized_level(self, level):
        return {"DBG": "DEBUG", "INF": "INFO", "ERR": "ERROR"}.get(level, level)


class _AgentStdout(_StdoutLogsInterfaceValidator):
    def __init__(self):
        super().__init__("agent")

        p = "(?P<{}>{})".format
        timestamp = p("timestamp", r"[^|]*")
        level = p("level", r"[A-Z]*")
        message = p("message", r".*")
        self._parsers.append(re.compile(rf"^{timestamp} *\| *[A-Z]* *\| *{level} *\| *{message}"))
        self._parsers.append(re.compile(message))  # fall back


class _PostgresStdout(_StdoutLogsInterfaceValidator):
    def __init__(self):
        super().__init__("postgres", new_log_line_pattern=r"^\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d.\d\d\d UTC \[\d+\]")

        p = "(?P<{}>{})".format

        timestamp = p("timestamp", r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d.\d\d\d UTC")
        level = p("level", r"[A-Z]+")
        message = p("message", r".*")
        self._parsers.append(re.compile(rf"^{timestamp} \[\d+\] {level}: *{message}"))
        self._parsers.append(re.compile(message))  # fall back


########################################################


class _LogPresence:
    def __init__(self, pattern, **extra_conditions):
        self.pattern = re.compile(pattern)
        self.extra_conditions = {k: re.compile(pattern) for k, pattern in extra_conditions.items()}

    def check(self, data):
        if "message" in data and self.pattern.search(data["message"]):
            for key, extra_pattern in self.extra_conditions.items():
                if key not in data:
                    logger.info(f"For {self}, {repr(self.pattern.pattern)} was found, but [{key}] field is missing")
                    logger.info(f"-> Log line is {data['message']}")
                    return

                if not extra_pattern.search(data[key]):
                    logger.info(
                        f"For {self}, {repr(self.pattern.pattern)} was found, but condition on [{key}] failed: "
                        f"'{extra_pattern.pattern}' != '{data[key]}'"
                    )
                    return

            logger.debug(f"For {self}, found {data['message']}")
            return True


class _LogAbsence:
    def __init__(self, pattern, allowed_patterns=None):
        self.pattern = re.compile(pattern)
        self.allowed_patterns = [re.compile(pattern) for pattern in allowed_patterns] if allowed_patterns else []
        self.failed_logs = []

    def check(self, data):
        if self.pattern.search(data["raw"]):

            for pattern in self.allowed_patterns:
                if pattern.search(data["raw"]):
                    return

            logger.error(json.dumps(data["raw"], indent=2))
            raise ValueError("Found unexpected log")


class Test:
    def test_main(self):
        """Test example"""

        from utils._context._scenarios import scenarios

        context.scenario = scenarios.default

        i = _PostgresStdout()
        i.configure(True)
        i.load_data()

        for item in i.get_data():
            print(item)


if __name__ == "__main__":
    Test().test_main()
