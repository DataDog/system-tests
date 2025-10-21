# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""

import re
from utils import weblog, interfaces, scenarios, features, context
from utils._decorators import missing_feature
from utils.interfaces._library.miscs import validate_process_tags


TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z")


@features.profiling
@features.dd_profiling_enabled
@scenarios.profiling
class Test_Profile:
    """Basic testing of profiling"""

    _is_set_up = False  # used to do the setup only once

    @staticmethod
    def _common_setup() -> None:
        if Test_Profile._is_set_up:
            return

        Test_Profile._is_set_up = True

        for _ in range(100):
            weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def setup_library(self):
        self._common_setup()

    def test_library(self):
        """All profiling libraries payload have start and end fields"""
        interfaces.library.validate_all(self._validate_data, path_filters="/profiling/v1/input")

    def setup_agent(self):
        self._common_setup()

    def test_agent(self):
        """All profiling agent payload have recording-start and recording-end fields"""
        interfaces.agent.validate_all(self._validate_data, path_filters="/api/v2/profile")

    def setup_process_tags(self):
        self._common_setup()

    @features.process_tags
    @missing_feature(
        condition=context.library.name != "java",
        reason="Not yet implemented",
    )
    def test_process_tags(self):
        """All profiling libraries payload have process tags field"""
        profiling_data_list = list(interfaces.agent.get_profiling_data())
        for data in profiling_data_list:
            for content in data["request"]["content"]:
                if "content" in content:
                    validate_process_tags(content["content"]["process_tags"])

    @staticmethod
    def _validate_data(data) -> None:
        content = data["request"]["content"]

        for part in content:
            headers = {k.lower(): v for k, v in part["headers"].items()}
            if 'name="event"' in headers.get("content-disposition", ""):
                part_content = part["content"]

                assert "start" in part_content, "No start field"
                assert "end" in part_content, "No end field"
                assert re.fullmatch(TIMESTAMP_PATTERN, part_content["start"])
                assert re.fullmatch(TIMESTAMP_PATTERN, part_content["end"])

                return

        raise ValueError("No profiling event requests")
