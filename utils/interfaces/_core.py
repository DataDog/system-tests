# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" This file contains base class used to validate interfaces """

import threading
import json
import re
import time
import warnings

from utils.tools import logger
from ._deserializer import deserialize


class InterfaceValidator:
    """Validate an interface

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

    def get_spans(self):
        for data in self.get_data(path_filters="/api/v0.2/traces"):
            if "tracerPayloads" not in data["request"]["content"]:
                raise Exception("Trace property is missing in agent payload")

            for payload in data["request"]["content"]["tracerPayloads"]:
                for trace in payload["chunks"]:
                    for span in trace["spans"]:
                        yield data, span

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
