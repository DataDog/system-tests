# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
import json
import re
from utils import weblog, interfaces, scenarios, features


TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z")


@features.profiling
@features.dd_profiling_enabled
@scenarios.profiling
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
        requests = list(interfaces.library.get_profiling_data())
        self._check_requests(requests)

    def setup_agent(self):
        self._common_setup()

    def test_agent(self):
        """All profiling agent payload have recording-start and recording-end fields"""
        requests = list(interfaces.agent.get_profiling_data())
        self._check_requests(requests)

    def _check_requests(self, requests):
        assert len(requests) > 0, "No profiling requests"

        # Requests are multipart, and content is a list
        requests = [r["request"]["content"] for r in requests]
        requests = [r for r in requests if isinstance(r, list)]
        # Flatten list
        requests = [r for sublist in requests for r in sublist]

        requests = [r for r in requests if 'name="event"' in r["headers"].get("Content-Disposition", "")]
        assert len(requests) > 0, "No profiling event requests"
        for req in requests:
            content = json.loads(req["content"])
            assert "start" in content, "No start field"
            assert "end" in content, "No end field"
            assert re.fullmatch(TIMESTAMP_PATTERN, content["start"])
            assert re.fullmatch(TIMESTAMP_PATTERN, content["end"])
