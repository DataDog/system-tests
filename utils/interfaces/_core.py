# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Contains base class used to validate interfaces"""

from collections.abc import Callable, Iterable
import json
from os import listdir
from os.path import join
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Any

import pytest

from utils._logger import logger
from utils.interfaces._schemas_validators import SchemaValidator, SchemaError


class InterfaceValidator:
    """Validate an interface

    One instance of this list handle only one interface
    """

    replay: bool
    """ True if the process is in replay mode """

    log_folder: str
    """ Folder where interfaces' logs are stored """

    host_log_folder: str
    """ Folder where all logs are stored """

    def __init__(self, name: str):
        self.name = name

    def configure(self, host_log_folder: str, *, replay: bool):
        self.replay = replay
        self.log_folder = f"{host_log_folder}/interfaces/{self.name}"
        self.host_log_folder = host_log_folder

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.name}')"

    def __str__(self):
        return f"{self.name} interface"


class ProxyBasedInterfaceValidator(InterfaceValidator):
    """Interfaces based on proxy container"""

    def __init__(self, name: str):
        super().__init__(name)

        self._wait_for_event = threading.Event()
        self._wait_for_function: Callable | None = None

        self._lock = threading.RLock()
        self._data_list: list[dict] = []
        self._ingested_files: set[str] = set()
        self._schema_errors: list[SchemaError] | None = None

    def configure(self, host_log_folder: str, *, replay: bool):
        super().configure(host_log_folder, replay=replay)

        if not replay:
            shutil.rmtree(self.log_folder, ignore_errors=True)
            Path(self.log_folder).mkdir(parents=True, exist_ok=True)
            Path(self.log_folder + "/files").mkdir(parents=True, exist_ok=True)

    def ingest_file(self, src_path: str):
        with self._lock:
            if src_path in self._ingested_files:
                return

            logger.debug(f"Ingesting {src_path}")

            with open(src_path, encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.decoder.JSONDecodeError:
                    # the file may not be finished
                    return

            self._append_data(data)
            self._ingested_files.add(src_path)

            # Ensure the list is completely sorted
            self._data_list.sort(key=lambda data: data["log_filename"])

        if self._wait_for_function and self._wait_for_function(data):
            self._wait_for_event.set()

    def wait(self, timeout: int):
        time.sleep(timeout)

    def check_deserialization_errors(self):
        """Verify that all proxy deserialization are successful"""

        for data in self._data_list:
            filename = data["log_filename"]
            if "content" not in data["request"]:
                traceback = data["request"].get("traceback", "no traceback")
                pytest.exit(reason=f"Unexpected error while deserialize {filename}:\n {traceback}", returncode=1)

            if data["response"] and "content" not in data["response"]:
                traceback = data["response"].get("traceback", "no traceback")
                pytest.exit(reason=f"Unexpected error while deserialize {filename}:\n {traceback}", returncode=1)

    def load_data_from_logs(self):
        for filename in sorted(listdir(self.log_folder)):
            file_path = join(self.log_folder, filename)
            if Path(file_path).is_file():
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)

                self._append_data(data)
                logger.info(f"{self.name} interface gets {file_path}")

    def _append_data(self, data: dict):
        self._data_list.append(data)

    def get_data(self, path_filters: Iterable[str] | str | None = None):
        if path_filters is not None:
            if isinstance(path_filters, str):
                path_filters = [path_filters]

            path_regexes = [re.compile(path) for path in path_filters]
        else:
            path_regexes = None

        for data in self._data_list:
            if path_regexes is not None and all(path.fullmatch(data["path"]) is None for path in path_regexes):
                continue

            yield data

    def validate_one(
        self,
        validator: Callable[[dict], bool],
        path_filters: Iterable[str] | str | None = None,
        *,
        allow_no_data: bool = False,
        success_by_default: bool = False,
    ) -> None:
        """Will call validator() on all data sent on path_filters. validator() returns a boolean :
        * True : the payload satisfies the condition, validate_one returns in success
        * False : the payload is ignored
        * If validator() raise an exception. the validate_one will fail

        If no payload satisfies validator(), then validate_one will fail
        """

        data_is_missing = True

        for data in self.get_data(path_filters=path_filters):
            data_is_missing = False
            try:
                if validator(data) is True:
                    return
            except Exception as e:
                logger.error(f"{data['log_filename']} did not validate this test")

                if isinstance(e, ValidationError):
                    if isinstance(e.extra_info, (dict, list)):
                        logger.info(json.dumps(e.extra_info, indent=2))
                    elif isinstance(e.extra_info, (str, int, float)):
                        logger.info(e.extra_info)

                raise

        if not allow_no_data and data_is_missing:
            raise ValueError(f"No data has been observed on {path_filters}")

        if not success_by_default:
            raise ValueError("Test has not been validated by any data")

    def validate_all(
        self,
        validator: Callable[[dict], None],
        path_filters: Iterable[str] | str | None = None,
        *,
        allow_no_data: bool = False,
    ) -> None:
        """Will call validator() on all data sent on path_filters
        If ever a validator raise an exception, the validation will fail
        """

        data_is_missing = True

        for data in self.get_data(path_filters=path_filters):
            data_is_missing = False
            try:
                validator(data)
            except Exception as e:
                logger.error(f"{data['log_filename']} did not validate this test")

                if isinstance(e, ValidationError):
                    if isinstance(e.extra_info, (dict, list)):
                        logger.info(json.dumps(e.extra_info, indent=2))
                    elif isinstance(e.extra_info, (str, int, float)):
                        logger.info(e.extra_info)

                raise

        if not allow_no_data and data_is_missing:
            raise ValueError(f"No data has been observed on {path_filters}")

    def wait_for(self, wait_for_function: Callable, timeout: int):
        if self.replay:
            return

        # first, try existing data
        with self._lock:
            for data in self._data_list:
                if wait_for_function(data):
                    logger.info(f"wait for {wait_for_function} finished in success with existing data")
                    return

            # then set the lock, and wait for append_data to release it
            self._wait_for_event.clear()
            self._wait_for_function = wait_for_function

        # release the main lock, and sleep !
        if self._wait_for_event.wait(timeout):
            logger.info(f"wait for {wait_for_function} finished in success")
        else:
            logger.error(f"Wait for {wait_for_function} finished in error")

        self._wait_for_function = None

    def get_schemas_errors(self) -> list[SchemaError]:
        if self._schema_errors is None:
            self._schema_errors: list[SchemaError] = []
            validator = SchemaValidator(self.name)

            for data in self.get_data():
                self._schema_errors.extend(validator.get_errors(data))

        return self._schema_errors

    def assert_response_header(
        self, path_filters: list[str] | str, header_name_pattern: str, header_value_pattern: str
    ) -> None:
        """Assert that a header, and its value are present in all requests for a given path
        header_name_pattern: a regular expression to match the header name (lower case)
        header_value_pattern: a regular expression to match the header value
        """

        self._assert_header(path_filters, "response", header_name_pattern, header_value_pattern)

    def assert_request_header(
        self, path_filters: list[str] | str, header_name_pattern: str, header_value_pattern: str
    ) -> None:
        """Assert that a header, and its value are present in all requests for a given path
        header_name_pattern: a regular expression to match the header name (lower case)
        header_value_pattern: a regular expression to match the header value
        """

        self._assert_header(path_filters, "request", header_name_pattern, header_value_pattern)

    def _assert_header(
        self,
        path_filters: list[str] | str,
        request_or_response: str,
        header_name_pattern: str,
        header_value_pattern: str,
    ) -> None:
        data = list(self.get_data(path_filters))

        logger.info(
            f"Check that {request_or_response} headers on {path_filters} "
            f"match {header_name_pattern}={header_value_pattern}"
        )

        if len(data) == 0:
            raise ValueError(f"No data found for {path_filters}")

        error_message = ""
        for item in data:
            log_prefix = f"{item['log_filename']} - {request_or_response}'s header {header_name_pattern}"
            header_values = [
                header[1]
                for header in item[request_or_response]["headers"]
                if re.fullmatch(header_name_pattern, header[0].lower())
            ]

            if len(header_values) == 0:
                error_message = f"{log_prefix}: not found"
                logger.error(error_message)

            for value in header_values:
                if not re.fullmatch(header_value_pattern, value):
                    error_message = f"{log_prefix}: {value} (expecting {header_value_pattern})"
                    logger.error(error_message)
                else:
                    logger.debug(f"{log_prefix}: {value}")

        if error_message:
            raise AssertionError(error_message)


class ValidationError(Exception):
    def __init__(self, *args: object, extra_info: Any = None) -> None:  # noqa: ANN401
        super().__init__(*args)
        self.extra_info = extra_info
