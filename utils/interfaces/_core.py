# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
This file contains base class used to validate interfaces
"""

import logging
import threading
import inspect
import gc
import json
import re

from utils.tools import get_logger, m, e as format_error, get_exception_traceback
from ._deserializer import deserialize

logger = get_logger("interfaces", use_dedicated_file=True)


class InterfaceValidator(object):
    """ Validate an interface

    Main thread use append_validation() method to AsyncValidation objects
    data_collector use append_data() method to add data from interfaces

    One instance of this list handle only one interface
    """

    def __init__(self, name):
        self.name = name

        self.message_counter = 0

        self._lock = threading.RLock()
        self._validations = []
        self._data_list = []
        self._closed = threading.Event()
        self._closed.set()
        self.is_success = False

        # if there is an excpetion during test execution on any other part then test itself
        # save it to display it on output. Very helpful when it comes to modify internals
        self.system_test_error = None

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.name}')"

    def __str__(self):
        return f"{self.name} interface validator"

    def _check_closed_status(self):
        if len([item for item in self._validations if not item.closed]) == 0:
            self._closed.set()

    # Main thread domain
    def wait(self, timeout):
        if self.system_test_error is not None:
            return

        logger.info(f"Wait for {self.name}'s interface validation for {timeout} seconds")
        self._closed.wait(timeout)

        try:
            with self._lock:
                fails = []

                for validation in self._validations:
                    try:
                        validation.final_check()
                    except Exception as exc:
                        traceback = "\n".join([format_error(l) for l in get_exception_traceback(exc)])
                        validation.set_failure(f"Unexpected error for {m(validation.message)}:\n{traceback}")

                    if not validation.closed:
                        validation.set_expired()

                    if not validation.is_success:
                        fails.append(validation)

                if len(fails) != 0:
                    self.is_success = False
                    return

        except Exception as e:
            self.system_test_error = e
            raise

        self.is_success = True

    @property
    def closed(self):
        return self._closed.is_set()

    def append_validation(self, validation):
        if self.system_test_error is not None:
            return

        validation._interface = self.name

        logger.debug(f"{repr(validation)} added in {self}[{len(self._validations)}]")

        try:
            with self._lock:
                self._validations.append(validation)
                self._closed.clear()

                for data in self._data_list:
                    if not validation.closed:
                        validation._check(data)
                        if validation.closed:
                            break

                self._check_closed_status()

        except Exception as e:
            self.system_test_error = e
            raise

    # data collector thread domain
    def append_data(self, data):
        logger.debug(f"{self.name}'s interface receive data on [{data['host']}{data['path']}]")

        if self.system_test_error is not None:
            return

        try:
            with self._lock:
                count = self.message_counter
                self.message_counter += 1
            deserialize(data, self.name)

            log_filename = f"logs/interfaces/{self.name}/{count:03d}_{data['path'].replace('/', '_')}.json"
            data["log_filename"] = log_filename

            with open(log_filename, "w") as f:
                json.dump(data, f, indent=2, cls=ObjectDumpEncoder)

            with self._lock:

                self._data_list.append(data)

                for i, validation in enumerate(self._validations):
                    logger.debug(f"Send [{data['host']}{data['path']}] data to #{i}: {validation}")
                    if not validation.closed:
                        validation._check(data)

                self._check_closed_status()
        except Exception as e:
            self.system_test_error = e
            raise

        return data

    def check(self, message):
        pass


class ObjectDumpEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, bytes):
            return str(o)
        return json.JSONEncoder.default(self, o)


class BaseValidation(object):
    """Base validation item"""

    _interface = None  # which interface will be validated
    is_success_on_expiry = False  # if validation is still pending at end of procees, is it a success?
    path_filters = None  # Can be a string, or a list of string. Will perfom validation only on path in it.

    def __init__(self, message=None, request=None):
        self.message = message
        self._closed = threading.Event()
        self._is_success = None

        if isinstance(self.path_filters, str):
            self.path_filters = [self.path_filters]

        if self.path_filters is not None:
            self.path_filters = [re.compile(path) for path in self.path_filters]

        if request is not None:
            self.rid = request.request.headers["User-Agent"][-36:]
        else:
            self.rid = None

        self.frame = None

        # save test context, if validation fails
        for frame_info in inspect.getouterframes(inspect.currentframe()):
            if frame_info.function.startswith("test_"):
                self.frame = frame_info
                if self.message is None:
                    # if the message is missing, try to get the function docstring
                    func_obj = gc.get_referrers(frame_info.frame.f_code)[0]
                    self.message = func_obj.__doc__

                    # if the message is missing, try to get the parent class docstring
                    if self.message is None and "self" in frame_info.frame.f_locals:
                        self.message = frame_info.frame.f_locals["self"].__doc__

                break

        if self.message is None:
            raise Exception(f"Please set a message for {self.frame.function}")

        self.logs = []

    def __str__(self):
        return f"Interface: {self._interface} -> {self.__class__.__name__}: {m(self.message)}"

    def __repr__(self):
        if self.rid:
            return f"{self.__class__.__name__}({repr(self.message)}, {self.rid})"
        else:
            return f"{self.__class__.__name__}({repr(self.message)})"

    def get_test_source_info(self):
        klass = self.frame.frame.f_locals["self"].__class__.__name__
        return self.frame.filename.replace("/app/", ""), klass, self.frame.function

    def log_debug(self, message):
        self._log(logging.DEBUG, message)

    def log_info(self, message):
        self._log(logging.INFO, message)

    def log_error(self, message):
        self._log(logging.ERROR, message)

    def _log(self, level, message):
        record = logger.makeRecord("", level, "", 0, message, None, None)
        self.logs.append(record)
        logger.handle(record)

    def wait(self, timeout):
        return self._closed.wait(timeout)

    @property
    def closed(self):
        return self._closed.is_set()

    @property
    def is_success(self):
        assert self.closed, f"{self} is not closed, can't give status"
        return self._is_success

    def set_status(self, is_success):
        self._is_success = is_success
        self._closed.set()

    def set_failure(self, message):
        self.log_error(message)
        self.set_status(False)

    def set_expired(self):
        if not self.closed:
            if not self.is_success_on_expiry:
                self.log_error(f"{self} has expired and is a failure")
            self.set_status(self.is_success_on_expiry)

    def _check(self, data):
        if self.path_filters is not None and all((path.fullmatch(data["path"]) is None for path in self.path_filters)):
            return

        self.check(data)

    def check(self, data):
        """Will be called every time a new data is seen threw the interface"""
        raise NotImplementedError()

    def final_check(self):
        """Will be called once, at the very end of the process"""
        pass

    def expect(self, condition: bool, err_msg):
        """Sets result to failed and returns True if condition is False, returns False otherwise"""
        if not condition:
            self.set_failure(err_msg)

        return not condition
