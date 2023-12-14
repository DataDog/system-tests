# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Test format specifications"""
import json

import requests

from jsonschema import validate
from utils import weblog, interfaces
from utils.tools import logger


SCHEMA_URL = "https://raw.githubusercontent.com/DataDog/schema/rarguelloF/SMTC-40/extend-agent-payload/semantic-core/v1/agent_payload_modified.json"


class Test_Schemas:
    """Agents's payload are valid regarding schemas"""

    def setup_full(self):
        # send some requests to be sure to trigger events
        weblog.get("/waf", params={"key": "\n :"})  # rules.http_protocol_violation.crs_921_160

    def test_agent_payload(self):
        resp = requests.get(SCHEMA_URL)
        resp.raise_for_status()
        schema = resp.json()

        # with open('/Users/rodrigo.arguello/go/src/github.com/DataDog/schema/semantic-core/v1/agent_payload.json') as json_file:
        #     schema = json.load(json_file)

        logger.debug(f"using schema {json.dumps(schema)}")

        for data in interfaces.agent.get_data():
            path = data["path"]
            if "traces" not in path:
                continue

            logger.debug(f"validating {json.dumps(data)}")
            content = data["request"]["content"]
            validate(instance=content, schema=schema)
