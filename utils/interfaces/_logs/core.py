# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Check data that are sent to logs file on weblog"""

import re
import os
from typing import DefaultDict

from utils import context
from utils.tools import logger
from utils.interfaces._core import BaseValidation, InterfaceValidator


class _LogsInterfaceValidator(InterfaceValidator):
    def __init__(self, name):
        super().__init__(name)

        self._skipped_patterns = [
            re.compile(r"^\s*$"),
        ]
        self._new_log_line_pattern = re.compile(r".")
        self._parsers = []

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

    def _get_standardized_level(self, level):
        return level

    def _read(self):
        for filename in self._get_files():
            logger.info(f"For {self}, reading {filename}")
            log_count = 0
            try:
                with open(filename, "r") as f:
                    buffer = []
                    for line in f:
                        if line.endswith("\n"):
                            line = line[:-1]  # remove tailing \n
                        line = self._clean_line(line)

                        if self._is_skipped_line(line):
                            continue

                        if self._is_new_log_line(line) and len(buffer):
                            log_count += 1
                            yield "\n".join(buffer) + "\n"
                            buffer = []

                        buffer.append(line)

                    log_count += 1
                    yield "\n".join(buffer) + "\n"

                logger.info(f"Reading {filename} is finished, {log_count} has been treated")
            except FileNotFoundError:
                logger.error(f"File not found: {filename}")

    def wait(self):
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

            self.append_data(parsed)

        super().wait(0)

    def append_data(self, data):
        if self.system_test_error is not None:
            return

        try:
            for validation in self._validations:
                if not validation.closed:
                    validation._check(data)

            self._check_closed_status()
        except Exception as e:
            self.system_test_error = e
            raise

    def __test__(self):
        self.wait()
        print(f"Interface result: {self.is_success}")
        for v in self._validations:
            if not v.is_success:
                for l in v.logs:
                    print(l)

    def assert_presence(self, pattern, **extra_conditions):
        self.append_validation(_LogPresence(pattern, **extra_conditions))

    def assert_absence(self, pattern):
        self.append_validation(_LogAbsence(pattern))

    def append_log_validation(self, validator):  # TODO rename
        self.append_validation(_LogValidation(validator))


class _LibraryStdout(_LogsInterfaceValidator):
    def __init__(self):
        super().__init__("Weblog stdout")

        p = "(?P<{}>{})".format

        self._skipped_patterns += [
            re.compile(r"^Attaching to systemtests_weblog_1$"),
            re.compile(r"systemtests_weblog_1 exited with code \d+"),
        ]

        if context.library == "java":
            self._skipped_patterns += [
                re.compile(r"^[ /\\_,''.()=`|]*$"),  # Java Spring ASCII art
                re.compile(r"^ +:: Spring Boot :: +\(v\d+.\d+.\d+(-SNAPSHOT)?\)$"),
            ]
            self._new_log_line_pattern = re.compile(r"^(\[dd.trace )?\d{4}-\d\d-\d\d")

            source = p("source", r"[a-z\.]+")
            timestamp = p("timestamp", r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d:\d\d\d [+\-]0000")
            thread = p("thread", r"[\w\-]+")
            level = p("level", r"\w+")
            klass = p("klass", r"[\w\.$]+")
            message = p("message", r".*")
            self._parsers.append(re.compile(fr"^\[{source} {timestamp}\] \[{thread}\] {level} {klass} - {message}"))

            timestamp = p("timestamp", r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d")
            klass = p("klass", r"[\w\.$\[\]/]+")
            self._parsers.append(re.compile(fr"^{timestamp} +{level} \d -+ \[ *{thread}\] +{klass} *: *{message}"))

        elif context.library == "dotnet":
            self._new_log_line_pattern = re.compile(r"^\s*(info|debug|error)")
        elif context.library == "php":
            self._skipped_patterns += [
                re.compile(r"^(?!\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\]\[[a-z]+\]\[\d+\])"),
            ]

            timestamp = p("timestamp", r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}")
            level = p("level", r"\w+")
            thread = p("thread", r"\d+")
            message = p("message", r".+")
            self._parsers.append(re.compile(fr"\[{timestamp}\]\[{level}\]\[{thread}\] {message}"))
        else:
            self._new_log_line_pattern = re.compile(r".")
            self._parsers.append(re.compile(p("message", r".*")))

    def _get_files(self):
        return ["logs/docker/weblog/stdout.log"]

    def _clean_line(self, line):
        if line.startswith("weblog_1         | "):
            line = line[19:]

        return line

    def _get_standardized_level(self, level):
        if context.library == "php":
            return level.upper()
        else:
            return super(_LibraryStdout, self)._get_standardized_level(level)


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
        thread = p("thread", r"[\w\-]+")
        level = p("level", r"\w+")
        message = p("message", r".*")
        self._parsers.append(re.compile(fr"^{timestamp} \[{level}\] {message}"))

    def _get_files(self):
        result = []

        for f in os.listdir("logs/docker/weblog/logs/"):
            filename = os.path.join("logs/docker/weblog/logs/", f)

            if os.path.isfile(filename) and re.search(r"dotnet-tracer-managed-dotnet-\d+.log", filename):
                result.append(filename)

        return result

    def _get_standardized_level(self, level):
        return {"DBG": "DEBUG", "INF": "INFO", "ERR": "ERROR"}.get(level, level)


########################################################


class _LogPresence(BaseValidation):
    def __init__(self, pattern, **extra_conditions):
        super().__init__()
        self.pattern = re.compile(pattern)
        self.extra_conditions = {k: re.compile(pattern) for k, pattern in extra_conditions.items()}

    def check(self, data):
        if "message" in data and self.pattern.search(data["message"]):
            for key, extra_pattern in self.extra_conditions.items():
                if key not in data:
                    self.log_info(f"For {self}, pattern was found, but condition on [{key}] was not found")
                    return
                elif not extra_pattern.search(data[key]):
                    self.log_info(
                        f"For {self}, pattern was found, but condition on [{key}] failed: "
                        f"'{extra_pattern.pattern}' != '{data[key]}'"
                    )
                    return

            self.log_debug(f"For {self}, found {data['message']}")
            self.set_status(True)


class _LogAbsence(BaseValidation):
    def __init__(self, pattern):
        super().__init__()
        self.pattern = re.compile(pattern)
        self.failed_logs = []

    def check(self, data):
        if self.pattern.search(data["raw"]):
            self.failed_logs.append(data["raw"])

    def final_check(self):
        if len(self.failed_logs) == 0:
            self.set_status(True)
            return

        aggregated_logs = DefaultDict(int)
        for l in self.failed_logs:
            cleaned = re.sub("^\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d \+\d\d:\d\d +", "", l)
            aggregated_logs[cleaned] += 1

        for log, count in aggregated_logs.items():
            if count != 1:
                self.log_error(f"I found {count} instances of this 😱:")

            self.log_error(log)

        self.set_status(False)


class _LogValidation(BaseValidation):
    """ will run an arbitrary check on log

        Validator function can :
        * returns true => validation will be validated at the end (but trace will continue to be checked)
        * returns False or None => nothing is done
        * raise an exception => validation will fail
    """

    def __init__(self, validator):
        super().__init__()
        self.validator = validator

    def check(self, data):
        try:
            if self.validator(data):
                self.is_success_on_expiry = True
        except Exception as e:
            self.set_failure(f"{self.message} not validated: {e}\nLog is: {data['raw']}")


class Test:
    def test_main(self):
        """ Test example """
        i = _LibraryStdout()
        i.assert_presence(r".*", level="DEBUG")
        i.__test__()


if __name__ == "__main__":
    Test().test_main()
