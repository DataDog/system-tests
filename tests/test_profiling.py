# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
import json
import re
from utils import weblog, interfaces, bug, scenarios, missing_feature


TIMESTAMP_PATTERN = re.compile(r"\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(.\d{3,6})?Z")


@bug(library="dotnet", reason="Need to understand how to activate profiling")
@bug(library="golang", reason="Need to understand how to activate profiling")
@bug(library="php", reason="Need to understand how to activate profiling")
@bug(library="python", reason="Need to understand how to activate profiling")
@bug(library="ruby", reason="Need to understand how to activate profiling")
@missing_feature(weblog_variant="vertx3", reason="Endpoint not implemented")
@missing_feature(weblog_variant="vertx4", reason="Endpoint not implemented")
@missing_feature(weblog_variant="akka-http", reason="Endpoint not implemented")
@scenarios.profiling
class Test_Profile:
    """ Basic testing of profiling """

    def _common_setup(self):
        if hasattr(self, "_is_set_up"):
            return
        self._is_set_up = True
        for _ in range(100):
            self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def setup_start_end(self):
        self._common_setup()

    def test_start_end(self):
        """ All profiling libraries payload have start and end fields"""
        requests = list(interfaces.library.get_profiling_data())
        assert len(requests) > 0, "No profiling requests"
        requests = [r for r in requests if 'name="event"' in r["request"]["headers"].get("Content-Disposition", "")]
        assert len(requests) > 0, "No profiling event requests"
        for req in requests:
            content = json.load(req["request"]["content"])
            assert "start" in content, "No start field"
            assert "end" in content, "No end field"
            assert re.fullmatch(TIMESTAMP_PATTERN, content["start"])
            assert re.fullmatch(TIMESTAMP_PATTERN, content["end"])

    def setup_agent(self):
        self._common_setup()

    @missing_feature(reason="Test not implemented")
    def test_agent(self):
        """ All profiling agent payload have recording-start and recording-end fields"""
        assert False
