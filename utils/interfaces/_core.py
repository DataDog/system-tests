# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" This file contains base class used to validate interfaces """

import threading
import inspect
import gc
import json
import re
import time
import warnings

from utils.tools import logger, m, e as format_error
from ._deserializer import deserialize


class InterfaceValidator:
    """Validate an interface

    Main thread use append_validation() method to AsyncValidation objects
    data_collector use append_data() method to add data from interfaces

    One instance of this list handle only one interface
    """

    def __init__(self, name):
        self.name = name

        self.message_counter = 0

        self._wait_for_event = threading.Event()
        self._wait_for_function = None

        self._lock = threading.RLock()
        self._data_list = []

        self.timeout = 0

        self.accept_data = True

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.name}')"

    def __str__(self):
        return f"{self.name} interface"

    def wait(self):
        time.sleep(self.timeout)
        self.accept_data = False

    # data collector thread domain
    def append_data(self, data):
        if not self.accept_data:
            return

        with self._lock:
            count = self.message_counter
            self.message_counter += 1

        log_filename = f"logs/interfaces/{self.name}/{count:03d}_{data['path'].replace('/', '_')}.json"
        data["log_filename"] = log_filename
        logger.debug(f"{self.name}'s interface receive data on {data['host']}{data['path']}: {log_filename}")

        deserialize(data, self.name)

        with open(log_filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, cls=ObjectDumpEncoder)

        self._data_list.append(data)

        if self._wait_for_function and self._wait_for_function(data):
            self._wait_for_event.set()

        return data

    def get_data(self, path_filters=None):

        if path_filters is not None:
            if isinstance(path_filters, str):
                path_filters = [path_filters]

            path_filters = [re.compile(path) for path in path_filters]

        for data in self._data_list:
            # Java sends empty requests during endpoint discovery
            if "request" in data and data["request"]["length"] == 0:
                continue

            if path_filters is not None and all((path.fullmatch(data["path"]) is None for path in path_filters)):
                continue

            yield data

    def validate(self, validator, path_filters=None, success_by_default=False):
        for data in self.get_data(path_filters=path_filters):
            try:
                if validator(data) is True:
                    return
            except Exception:
                logger.error(f"{data['log_filename']} did not validate this test")
                raise

        if not success_by_default:
            raise Exception("Test has not been validated by any data")

    def add_validation(self, validator, is_success_on_expiry=False, path_filters=None):
        warnings.warn("add_validation() is deprecated, please use validate()", DeprecationWarning)
        self.validate(validator=validator, path_filters=path_filters, success_by_default=is_success_on_expiry)

    def append_validation(self, validation):

        validation.interface = self.name

        for data in self.get_data(validation.path_filters):
            if validation.check(data):
                return

        if not validation.closed:
            validation.final_check()

        if not validation.is_success_on_expiry and not validation.is_success:
            raise Exception("???")

    def add_assertion(self, condition):
        warnings.warn("add_assertion() is deprecated, please use bare assert", DeprecationWarning)
        assert condition

    def add_final_validation(self, validator):
        warnings.warn("add_final_validation() is deprecated, simply call your validator", DeprecationWarning)
        assert validator()

    def wait_for(self, wait_for_function, timeout):

        # first, try existing data
        with self._lock:
            for data in self._data_list:
                if wait_for_function(data):
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


class ObjectDumpEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, bytes):
            return str(o)
        return json.JSONEncoder.default(self, o)


class BaseValidation:
    """Base validation item"""

    interface = None  # which interface will be validated
    is_success_on_expiry = False  # if validation is still pending at end of procees, is it a success?
    path_filters = None  # Can be a string, or a list of string. Will perfom validation only on path in it.

    def __init__(self, request=None, is_success_on_expiry=None, path_filters=None):
        # keep this two mumber on top, it's used in repr
        self.message = ""
        self.rid = None

        self._is_success = None

        if is_success_on_expiry is not None:
            self.is_success_on_expiry = is_success_on_expiry

        if path_filters is not None:
            self.path_filters = path_filters

        if isinstance(self.path_filters, str):
            self.path_filters = [self.path_filters]

        if self.path_filters is not None:
            self.path_filters = [re.compile(path) for path in self.path_filters]

        self.rid = get_rid_from_request(request)

        self.frame = None
        self.calling_method = None

        # Get calling class and calling method
        for frame_info in inspect.getouterframes(inspect.currentframe()):

            if frame_info.function.startswith("test_"):
                self.frame = frame_info
                gc.collect()
                self.calling_method = gc.get_referrers(frame_info.frame.f_code)[0]
                self.calling_class = frame_info.frame.f_locals["self"].__class__
                break

        if self.calling_method is None:
            raise Exception(f"Unexpected error, can't found the method for {self}")

        # try to get the function docstring
        self.message = self.calling_method.__doc__

        # if the message is missing, try to get the parent class docstring
        if self.message is None:
            self.message = self.calling_class.__doc__

        if self.message is None:
            raise Exception(f"Please set a message for {self.frame.function}")

        # remove new lines, duplicated spaces and tailing/heading spaces for logging
        self.message = self.message.replace("\n", " ").strip()
        self.message = re.sub(r" {2,}", " ", self.message)

        self.message = self.message.strip()

    def __str__(self):
        return f"Interface: {self.interface} -> {self.__class__.__name__}: {m(self.message)}"

    def __repr__(self):
        if self.rid:
            return f"{self.__class__.__name__}({repr(self.message)}, {self.rid})"

        return f"{self.__class__.__name__}({repr(self.message)})"

    def get_test_source_info(self):
        klass = self.calling_class.__name__
        return self.frame.filename.replace("/app/", ""), klass, self.frame.function

    def log_debug(self, message):
        logger.debug(message)

    def log_info(self, message):
        logger.info(message)

    def log_error(self, message):
        logger.error(message)

    @property
    def closed(self):
        return self._is_success is not None

    @property
    def is_success(self):
        return self._is_success

    def set_status(self, is_success):
        if not is_success:
            raise Exception(self.message)

        self._is_success = is_success

    def set_failure(self, message="", exception="", data=None, extra_info=None):
        if not message:

            message = f"{m(self.message)} is not validated: {format_error(str(exception))}"

            if data and isinstance(data, dict) and "log_filename" in data:
                message += f"\n\t Failing payload is in {data['log_filename']}"

            if not extra_info and hasattr(exception, "extra_info"):
                extra_info = exception.extra_info

            if extra_info:
                if isinstance(extra_info, (dict, list)):
                    extra_info = json.dumps(extra_info, indent=2)

                extra_info = str(extra_info)

                message += "\n" + "\n".join([f"\t{l}" for l in extra_info.split("\n")])

        raise Exception(message)

    def set_expired(self):
        if not self.closed:
            if not self.is_success_on_expiry:
                raise Exception(self.message)

    def check(self, data):
        """Will be called every time a new data is seen threw the interface"""
        raise NotImplementedError()

    def final_check(self):
        """Will be called once, at the very end of the process"""

    def expect(self, condition: bool, err_msg):
        """Sets result to failed and returns True if condition is False, returns False otherwise"""
        if not condition:
            self.set_failure(err_msg)

        return not condition


class ValidationError(Exception):
    def __init__(self, *args: object, extra_info=None) -> None:
        super().__init__(*args)
        self.extra_info = extra_info


def get_rid_from_request(request):
    if request is None:
        return None

    user_agent = [v for k, v in request.request.headers.items() if k.lower() == "user-agent"][0]
    return user_agent[-36:]


def get_rid_from_span(span):

    if not isinstance(span, dict):
        logger.error(f"Span should be an object, not {type(span)}")
        return None

    meta = span.get("meta", {})

    user_agent = None

    if span.get("type") == "rpc":
        user_agent = meta.get("grpc.metadata.user-agent")
        # java does not fill this tag; it uses the normal http tags

    if not user_agent:
        # code version
        user_agent = meta.get("http.request.headers.user-agent")

    if not user_agent:  # try something for .NET
        user_agent = meta.get("http_request_headers_user-agent")

    if not user_agent:  # last hope
        user_agent = meta.get("http.useragent")

    return get_rid_from_user_agent(user_agent)


def get_rid_from_user_agent(user_agent):
    if not user_agent:
        return None

    match = re.search("rid/([A-Z]{36})", user_agent)

    if not match:
        return None

    return match.group(1)
