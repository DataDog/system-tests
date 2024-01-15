# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Test format specifications"""
import base64
import json

import requests

from jsonschema import Draft202012Validator
from utils import weblog, interfaces
from utils.tools import logger


SCHEMA_URL = "https://raw.githubusercontent.com/DataDog/schema/rarguelloF/SMTC-40/extend-agent-payload/semantic-core/v1/agent_payload_modified.json"


# _format_as_index returns a formatted string from the given path.
# Example: "instance['tracerPayloads'][0]['chunks'][2]['spans'][0]['meta']"
def _format_as_index(obj_name, path, skip=None):
    if skip is None:
        skip = []

    if not path:
        return obj_name

    p = [index for index in path if index not in skip]
    return f"{obj_name}[{']['.join(repr(index) for index in p)}]"


class Test_Schemas:
    """Agents's payload are valid regarding schemas"""

    def setup_agent(self):
        # send some requests to be sure to trigger events
        weblog.get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160

    def test_agent(self):
        resp = requests.get(SCHEMA_URL)
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
                    "instance_path": _format_as_index("instance", e.relative_path),
                    "schema_path": _format_as_index(
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
            raise Exception(f"JSON Schema validation failed:\n{json.dumps(all_errors, indent=4)}")


class Test_SensitiveData:
    """Sensitive data is properly obfuscated."""

    # TODO: this will be fetched from the semantic-core schema definitions
    sensitive_fields = ["http.url"]

    def setup_http_url(self):
        self.r = weblog.get("/semantic-core/sensitive-data/http-url", auth=("user", "pass"))

    def test_http_url(self):
        assert self.r.status_code == 200
        logger.debug(f"got response: {self.r.text}")

        resp = json.loads(self.r.text)
        assert resp["status"] == "OK"

        client_spans = []
        server_spans = []

        for data in interfaces.agent.get_data():
            path = data["path"]
            if "traces" not in path:
                continue

            for payload in data["request"]["content"]["tracerPayloads"]:
                for chunk in payload["chunks"]:
                    for span in chunk["spans"]:
                        if span["service"] == "sensitive-data-client":
                            client_spans.append(span)
                        if span["service"] == "sensitive-data-server":
                            server_spans.append(span)

        assert len(client_spans) > 0
        assert len(server_spans) > 0

        for span in client_spans:
            self.assert_client_span(span)

        for span in server_spans:
            self.assert_server_span(span)

    def assert_client_span(self, span):
        logger.debug(f"validating client span: {json.dumps(span)}")

        for f in self.sensitive_fields:
            logger.debug(f"validating field: {f}")
            meta = span["meta"]

            if f in meta:
                logger.debug(f'validating field: "{f}={meta[f]}"')
                assert "user" not in meta[f]
                assert "pass" not in meta[f]
                # TODO: verify if this is the expected behavior, since query params are
                #  redacted in server spans but not in the client
                # assert '/token?<redacted>' in meta[f]

    def assert_server_span(self, span):
        logger.debug(f"validating server span: {json.dumps(span)}")

        # ensure the request was actually sending sensitive data in different places.
        meta = span["meta"]
        assert "system_test.raw_request" in meta
        assert "system_test.basic_auth.user" in meta
        assert "system_test.basic_auth.pass" in meta

        assert meta["system_test.basic_auth.user"] == "user"
        assert meta["system_test.basic_auth.pass"] == "pass"
        b64_credentials = base64.b64encode(bytes("user:pass", "utf-8")).decode("utf-8")

        assert f"Authorization: Basic {b64_credentials}" in meta["system_test.raw_request"]
        assert "/token?token=my-secret-token" in meta["system_test.raw_request"]

        for f in self.sensitive_fields:
            logger.debug(f"validating field: {f}")
            meta = span["meta"]

            if f in meta:
                logger.debug(f'validating field: "{f}={meta[f]}"')
                assert "user" not in meta[f]
                assert "pass" not in meta[f]
                assert "/token?<redacted>" in meta[f]
