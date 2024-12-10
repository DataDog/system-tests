# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""

import re
from utils import weblog, interfaces, scenarios, features, bug, context


TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z")


@features.profiling
@features.dd_profiling_enabled
@scenarios.profiling
@bug(context.library >= "python@2.18.0-dev", reason="PROF-11018")
class Test_Profile:
    """Basic testing of profiling"""

    @staticmethod
    def _common_setup():
        if hasattr(Test_Profile, "_is_set_up"):
            return

        Test_Profile._is_set_up = True

        for _ in range(100):
            weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def setup_library(self):
        self._common_setup()

    def test_library(self):
        """All profiling libraries payload have start and end fields"""
        interfaces.library.validate_profiling(self._validate_data)

    def setup_agent(self):
        self._common_setup()

    def test_agent(self):
        """All profiling agent payload have recording-start and recording-end fields"""
        interfaces.agent.validate_profiling(self._validate_data)

    @staticmethod
    def _validate_data(data):
        content = data["request"]["content"]

        for part in content:
            headers = {k.lower(): v for k, v in part["headers"].items()}
            if 'name="event"' in headers.get("content-disposition", ""):
                part_content = part["content"]

                assert "start" in part_content, "No start field"
                assert "end" in part_content, "No end field"
                assert re.fullmatch(TIMESTAMP_PATTERN, part_content["start"])
                assert re.fullmatch(TIMESTAMP_PATTERN, part_content["end"])

                return True

        raise ValueError("No profiling event requests")
