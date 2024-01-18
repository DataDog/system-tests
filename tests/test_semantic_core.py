# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json

import requests

from jsonschema import Draft202012Validator
from utils import weblog, interfaces, features
from utils.tools import logger


@features.semantic_core_validations
class Test_Schemas:
    """Test Agent payloads are valid regarding schemas"""

    def _setup(self):
        # send some requests to be sure to trigger events
        weblog.get("/waf", params={"key": "\n :"})

    setup_v1 = _setup

    def test_v1(self):
        self._run(self._schema_url("1.1.0"))

    def _run(self, schema_url):
        resp = requests.get(schema_url)
        resp.raise_for_status()
        schema = resp.json()

        logger.debug(f"using schema {json.dumps(schema)}")
        validator = Draft202012Validator(schema)
        all_errors = []

        for data in interfaces.agent.get_data():
            path = data["path"]
            if "traces" not in path:
                continue

            logger.debug(f"validating {json.dumps(data)}")
            content = data["request"]["content"]

            errors = [
                {
                    "message": e.message,
                    "instance_path": self._format_as_index("instance", e.relative_path),
                    "schema_path": self._format_as_index(
                        "schema",
                        list(e.relative_schema_path)[:-1],
                        skip=["properties", "items"],  # these are redundant for the schema
                    ),
                }
                for e in list(sorted(validator.iter_errors(instance=content), key=str))
            ]

            if errors:
                all_errors.append({"instance": content, "errors": errors})

        if all_errors:
            raise Exception(f"JSON Schema validation failed: {json.dumps(all_errors, indent=2)}")

    # _format_as_index returns a formatted string from the given path.
    # Example: "instance['tracerPayloads'][0]['chunks'][2]['spans'][0]['meta']"
    @staticmethod
    def _format_as_index(obj_name, path, skip=None):
        if skip is None:
            skip = []

        if not path:
            return obj_name

        p = [index for index in path if index not in skip]
        return f"{obj_name}[{']['.join(repr(index) for index in p)}]"

    @staticmethod
    def _schema_url(version):
        return f"https://raw.githubusercontent.com/DataDog/schema/rarguelloF/AIT-9507/extend-agent-payload/semantic-core/schema/releases/{version}/agent_payload.json"
