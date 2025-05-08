# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Check data that are sent to logs file on weblog"""

from collections.abc import Callable
import json
import os
from pathlib import Path
import re

from utils._logger import logger
from utils.interfaces._core import InterfaceValidator
from utils._context.component_version import ComponentVersion


class _LogsInterfaceValidator(InterfaceValidator):
    def __init__(self, name: str, new_log_line_pattern: str | None = None):
        super().__init__(name)

        self._skipped_patterns = [
            re.compile(r"^\s*$"),
        ]
        self._new_log_line_pattern = re.compile(new_log_line_pattern or ".")
        self._parsers: list[re.Pattern] = []
        self.timeout = 0
        self._data_list: list[dict] = []

    def _get_files(self):
        raise NotImplementedError

    def _clean_line(self, line: str):
        return line

    def _is_new_log_line(self, line: str):
        return self._new_log_line_pattern.search(line)

    def _is_skipped_line(self, line: str):
        return any(pattern.search(line) for pattern in self._skipped_patterns)

    def _get_standardized_level(self, level: str):
        return level

    def _read(self):
        for filename in self._get_files():
            logger.info(f"For {self}, reading {filename}")
            log_count = 0
            try:
                with open(filename, encoding="utf-8") as f:
                    buffer: list[str] = []
                    for raw_line in f:
                        line = raw_line
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

    def validate(self, validator: Callable, *, success_by_default: bool = False):
        for data in self.get_data():
            try:
                if validator(data) is True:
                    return
            except Exception:
                logger.error(f"{data} did not validate this test")
                raise

        if not success_by_default:
            raise ValueError("Test has not been validated by any data")

    def assert_presence(self, pattern: str, **extra_conditions: str):
        validator = _LogPresence(pattern, **extra_conditions)
        self.validate(validator.check, success_by_default=False)

    def assert_absence(self, pattern: str, allowed_patterns: list[str] | tuple[str, ...] = ()):
        validator = _LogAbsence(pattern, allowed_patterns)
        self.validate(validator.check, success_by_default=True)


class _StdoutLogsInterfaceValidator(_LogsInterfaceValidator):
    def __init__(self, container_name: str, new_log_line_pattern: str | None = None):
        super().__init__(f"{container_name} stdout", new_log_line_pattern=new_log_line_pattern)
        self.container_name = container_name

    def _get_files(self):
        return [
            f"{self.host_log_folder}/docker/{self.container_name}/stdout.log",
            f"{self.host_log_folder}/docker/{self.container_name}/stderr.log",
        ]


class _LibraryStdout(_StdoutLogsInterfaceValidator):
    def __init__(self):
        super().__init__("weblog")
        self.library = None

    def init_patterns(self, library: ComponentVersion):
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
        elif library == "cpp_nginx":
            self._new_log_line_pattern = re.compile(r".")
            timestamp = p("timestamp", r"\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}")
            level = p("level", r"\w+")
            thread = p("thread", r"\d+#\d+")
            message = p("message", r".+")
            self._parsers.append(re.compile(rf"^{timestamp} \[{level}\] {thread}: {message}"))
        elif library == "php":
            self._skipped_patterns += [
                re.compile(
                    # Ensure env vars are not leaked in logs
                    # Ex: export SOME_SECRET_ENV=api_key OR env[SOME_SECRET_ENV] = api_key
                    r"export \w+\s*=\s*.*|" r"env\[\w+\]\s*=.*"
                ),
            ]

            timestamp = p("timestamp", r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}")
            level = p("level", r"\w+")
            thread = p("thread", r"\d+")
            message = p("message", r".+")
            self._parsers.append(re.compile(rf"\[{timestamp}\]\[{level}\]\[{thread}\] {message}"))
        else:
            self._new_log_line_pattern = re.compile(r".")
            self._parsers.append(re.compile(p("message", r".*")))

    def _clean_line(self, line: str):
        if line.startswith("weblog_1         | "):
            line = line[19:]

        return line

    def _get_standardized_level(self, level: str):
        if self.library in ("php", "cpp_nginx"):
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
            files = os.listdir(f"{self.host_log_folder}/docker/weblog/logs/")
        except FileNotFoundError:
            files = []

        for f in files:
            filename = os.path.join(f"{self.host_log_folder}/docker/weblog/logs/", f)

            if Path(filename).is_file() and re.search(r"dotnet-tracer-managed-dotnet-\d+(_\d+)?.log", filename):
                result.append(filename)

        return result

    def _get_standardized_level(self, level: str):
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
    def __init__(self, pattern: str, **extra_conditions: str):
        self.pattern = re.compile(pattern)
        self.extra_conditions = {k: re.compile(pattern) for k, pattern in extra_conditions.items()}

    def check(self, data: dict):
        if "message" in data and self.pattern.search(data["message"]):
            for key, extra_pattern in self.extra_conditions.items():
                if key not in data:
                    logger.info(f"For {self}, {self.pattern.pattern!r} was found, but [{key}] field is missing")
                    logger.info(f"-> Log line is {data['message']}")
                    return None

                if not extra_pattern.search(data[key]):
                    logger.info(
                        f"For {self}, {self.pattern.pattern!r} was found, but condition on [{key}] failed: "
                        f"'{extra_pattern.pattern}' != '{data[key]}'"
                    )
                    return None

            logger.debug(f"For {self}, found {data['message']}")
            return True

        return None


class _LogAbsence:
    def __init__(self, pattern: str, allowed_patterns: list[str] | tuple[str, ...] = ()):
        self.pattern = re.compile(pattern)
        self.allowed_patterns = [re.compile(pattern) for pattern in allowed_patterns]

    def check(self, data: dict):
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
        from utils import context

        context.scenario = scenarios.default

        i = _PostgresStdout()
        i.configure(scenarios.default.host_log_folder, replay=True)
        i.load_data()

        for item in i.get_data():
            print(item)  # noqa: T201


if __name__ == "__main__":
    Test().test_main()
