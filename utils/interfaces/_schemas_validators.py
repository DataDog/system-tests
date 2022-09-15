# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
Usage:
    PYTHONPATH=. python utils/interfaces/_schemas_validators.py
"""

import os
import json
import re
import functools

from jsonschema import Draft7Validator, RefResolver, draft7_format_checker, exceptions as jsonschema_exceptions
from jsonschema.validators import extend
from utils.interfaces._core import BaseValidation


def _is_bytes_or_string(_checker, instance):
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "string") or isinstance(instance, bytes)


_type_checker = Draft7Validator.TYPE_CHECKER.redefine("string", _is_bytes_or_string)
_ApiObjectValidator = extend(Draft7Validator, type_checker=_type_checker)


def _get_schemas_filenames():
    for dir in (
        "utils/interfaces/schemas/library/",
        "utils/interfaces/schemas/agent/",
        "utils/interfaces/schemas/miscs/",
    ):
        for root, _, files in os.walk(dir):
            for f in files:
                if f.endswith(".json"):
                    yield os.path.join(root, f)


@functools.lru_cache()
def _get_schemas_store():
    """returns a dict with all defined schemas"""

    store = {}

    for filename in _get_schemas_filenames():
        schema = json.load(open(filename))

        assert "$id" in schema, filename
        assert schema["$id"] == filename[len("utils/interfaces/schemas") :], filename

        Draft7Validator.check_schema(schema)

        store[schema["$id"]] = schema

    return store


@functools.lru_cache()
def _get_schema_validator(schema_id):
    store = _get_schemas_store()

    if schema_id not in store:
        raise FileNotFoundError(f"There is no schema file that describe {schema_id}")

    schema = store[schema_id]
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    return _ApiObjectValidator(schema, resolver=resolver, format_checker=draft7_format_checker)


class SchemaValidator(BaseValidation):
    is_success_on_expiry = True

    def __init__(self, interface, allowed_errors):
        super().__init__()
        self.interface = interface
        self.allowed_errors = []

        for pattern in allowed_errors or []:
            self.allowed_errors.append(re.compile(pattern))

    def check(self, data):
        path = "/" if data["path"] == "" else data["path"]
        schema_id = f"/{self.interface}{path}-request.json"

        try:
            validator = _get_schema_validator(schema_id)
            if not validator.is_valid(data["request"]["content"]):
                messages = []

                for error in validator.iter_errors(data["request"]["content"]):
                    message = f"{error.message} on instance " + "".join([f"[{repr(i)}]" for i in error.path])
                    if not any([pattern.fullmatch(message) for pattern in self.allowed_errors]):
                        messages.append(message)

                if len(messages) != 0:
                    self.set_status(False)
                    self.log_error(f"In message {data['log_filename']}:")
                    for message in messages:
                        self.log_error(f"* {message}")

        except FileNotFoundError as e:
            self.set_failure(e)

        except jsonschema_exceptions.ValidationError as e:
            self.set_failure(e)


def _main(interface):

    path = f"logs/interfaces/{interface}"

    for f in os.listdir(path):
        data_path = os.path.join(path, f)
        print(f"  * {data_path}")
        if os.path.isfile(data_path):
            systemtest_interface_log_data = json.load(open(data_path, "r"))

            # We re-use BaseValidation sub class SchemaValidator to avoid logic duplication
            # but we need to stick to in BaseValidation internals...

            validator = SchemaValidator(interface)
            validator.check(systemtest_interface_log_data)
            validator.set_expired()

            if not validator.is_success:
                print("    ---> ERROR:")
                print("")
                for log in validator.logs:
                    print(log)


if __name__ == "__main__":
    print("# Validate logs output from system tests")
    _main("library")
    _main("agent")
