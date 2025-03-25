# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Usage:
PYTHONPATH=. python utils/interfaces/_schemas_validators.py
"""

from dataclasses import dataclass
import functools
import json
import os
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft7Validator, RefResolver, ValidationError
from jsonschema.validators import extend


def _is_bytes_or_string(_checker: Any, instance: Any):  # noqa: ANN401
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "string") or isinstance(instance, bytes)


_type_checker = Draft7Validator.TYPE_CHECKER.redefine("string", _is_bytes_or_string)
_ApiObjectValidator = extend(Draft7Validator, type_checker=_type_checker)


def _get_schemas_filenames():
    for schema_dir in (
        "utils/interfaces/schemas/library/",
        "utils/interfaces/schemas/agent/",
        "utils/interfaces/schemas/miscs/",
    ):
        for root, _, files in os.walk(schema_dir):
            for f in files:
                if f.endswith(".json"):
                    yield os.path.join(root, f)


@functools.lru_cache
def _get_schemas_store():
    """Returns a dict with all defined schemas"""

    store = {}

    for filename in _get_schemas_filenames():
        with open(filename, encoding="utf-8") as f:
            schema = json.load(f)

        assert "$id" in schema, filename
        assert schema["$id"] == filename[len("utils/interfaces/schemas") :], filename

        Draft7Validator.check_schema(schema)

        store[schema["$id"]] = schema

    return store


@functools.lru_cache
def _get_schema_validator(schema_id: str):
    store = _get_schemas_store()

    if schema_id not in store:
        raise FileNotFoundError(f"There is no schema file that describe {schema_id}")

    schema = store[schema_id]
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    return _ApiObjectValidator(schema, resolver=resolver, format_checker=Draft7Validator.FORMAT_CHECKER)


@dataclass
class SchemaError:
    interface_name: str
    endpoint: str
    error: ValidationError
    data: dict

    @property
    def message(self):
        return f"{self.data['log_filename']}: {self.error.message} on instance {self.error.json_path}"

    @property
    def data_path(self):
        return re.sub(r"\[\d+\]", "[]", self.error.json_path)


class SchemaValidator:
    def __init__(self, interface_name: str, allowed_errors: list[str] | tuple[str, ...] = ()):
        self.interface = interface_name
        self.allowed_errors = []

        for pattern in allowed_errors:
            self.allowed_errors.append(re.compile(pattern))

    def get_errors(self, data: dict) -> list[SchemaError]:
        path = "/" if data["path"] == "" else data["path"]
        schema_id = f"/{self.interface}{path}-request.json"

        if schema_id not in _get_schemas_store():
            return []

        validator = _get_schema_validator(schema_id)
        if "content" not in data["request"]:
            # something went wrong on the proxy side
            # it's not the schema job to complain about it
            return []

        if validator.is_valid(data["request"]["content"]):
            return []

        return [
            SchemaError(interface_name=self.interface, endpoint=path, error=error, data=data)
            for error in validator.iter_errors(data["request"]["content"])
        ]


def _main():
    for interface in ("agent", "library"):
        validator = SchemaValidator(interface)
        folders = [folder for folder in os.listdir(".") if Path(folder).is_dir() and folder.startswith("logs")]
        for folder in folders:
            path = f"{folder}/interfaces/{interface}"

            if not Path(path).exists():
                continue
            files = [file for file in os.listdir(path) if Path(os.path.join(path, file)).is_file()]
            for file in files:
                with open(os.path.join(path, file), encoding="utf-8") as f:
                    data = json.load(f)

                if "request" in data and data["request"]["length"] != 0:
                    for error in validator.get_errors(data):
                        print(error.message)  # noqa: T201


if __name__ == "__main__":
    _main()
