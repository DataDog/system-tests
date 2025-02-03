# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Contains base class used to validate interfaces"""

import json
from os import listdir
from os.path import join
from pathlib import Path
import re
import shutil
import threading
import time

import pytest

from utils.tools import logger
from utils.interfaces._schemas_validators import SchemaValidator, SchemaError


class InterfaceValidator:
    """Validate an interface

    One instance of this list handle only one interface
    """

    replay: bool
    """ True if the process is in replay mode """

    log_folder: str
    """ Folder where interfaces' logs are stored """

    def __init__(self, name):
        self.name = name

    def configure(self, host_log_folder, replay):
        self.replay = replay
        self.log_folder = f"{host_log_folder}/interfaces/{self.name}"

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.name}')"

    def __str__(self):
        return f"{self.name} interface"


class ProxyBasedInterfaceValidator(InterfaceValidator):
    """Interfaces based on proxy container"""

    def __init__(self, name):
        super().__init__(name)

        self._wait_for_event = threading.Event()
        self._wait_for_function = None

        self._lock = threading.RLock()
        self._data_list = []
        self._ingested_files = set()
        self._schema_errors = None

    def configure(self, host_log_folder, replay):
        super().configure(host_log_folder, replay)

        if not replay:
            shutil.rmtree(self.log_folder, ignore_errors=True)
            Path(self.log_folder).mkdir(parents=True, exist_ok=True)
            Path(self.log_folder + "/files").mkdir(parents=True, exist_ok=True)

    def ingest_file(self, src_path):
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

            # make 100% sure that the list is sorted
            self._data_list.sort(key=lambda data: data["log_filename"])

        if self._wait_for_function and self._wait_for_function(data):
            self._wait_for_event.set()

    def wait(self, timeout):
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

    def _append_data(self, data):
        self._data_list.append(data)

    def get_data(self, path_filters=None):
        if path_filters is not None:
            if isinstance(path_filters, str):
                path_filters = [path_filters]

            path_filters = [re.compile(path) for path in path_filters]

        for data in self._data_list:
            if path_filters is not None and all(path.fullmatch(data["path"]) is None for path in path_filters):
                continue

            yield data

    def validate(self, validator, path_filters=None, *, success_by_default=False):
        for data in self.get_data(path_filters=path_filters):
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

        if not success_by_default:
            raise ValueError("Test has not been validated by any data")

    def wait_for(self, wait_for_function, timeout):
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
            self._schema_errors = []
            validator = SchemaValidator(self.name)

            for data in self.get_data():
                self._schema_errors.extend(validator.get_errors(data))

        return self._schema_errors

    def assert_schema_point(self, endpoint, data_path):
        has_error = False

        for error in self.get_schemas_errors():
            if error.endpoint == endpoint and error.data_path == data_path:
                has_error = True
                logger.error(f"* {error.message}")

        assert not has_error, f"Schema is invalid for endpoint {endpoint} on data path {data_path}"

    def assert_schema_points(self, excluded_points=None):
        has_error = False
        excluded_points = excluded_points or []

        for error in self.get_schemas_errors():
            if (error.endpoint, error.data_path) in excluded_points:
                continue

            has_error = True
            logger.error(f"* {error.message}")

        assert not has_error, f"Schema validation failed for {self.name}"

    def assert_request_header(self, path, header_name_pattern: str, header_value_pattern: str) -> None:
        """Assert that a header, and its value are present in all requests for a given path
        header_name_pattern: a regular expression to match the header name (lower case)
        header_value_pattern: a regular expression to match the header value
        """

        data_found = False

        for data in self.get_data(path):
            data_found = True

            found = False

            for header, value in data["request"]["headers"]:
                if re.fullmatch(header_name_pattern, header.lower()):
                    if not re.fullmatch(header_value_pattern, value):
                        logger.error(f"Header {header} found in {data['log_filename']}, but value is {value}")
                    else:
                        found = True
                        continue

            if not found:
                raise ValueError(f"{header_name_pattern} not found (or incorrect) in {data['log_filename']}")

        if not data_found:
            raise ValueError(f"No data found for {path}")


class ValidationError(Exception):
    def __init__(self, *args: object, extra_info=None) -> None:
        super().__init__(*args)
        self.extra_info = extra_info
