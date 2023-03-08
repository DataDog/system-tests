# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
from utils import weblog, context, interfaces, bug, scenario, irrelevant


TIMESTAMP_PATTERN = r"\d\d\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(.\d{3,6})?Z"


@irrelevant(context.library != "cpp", reason="This can probably be added to other profilers")
@scenario("PROFILING")
class Test_Profile:
    """ Basic testing of profiling """

    def setup_start_end(self):
        # generate traffic
        for lp in range(100):
            self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def test_start_end(self):
        """ All profiling libraries payload have recording-start and recording-end fields"""
        interfaces.library.profiling_assert_field("start", content_pattern=TIMESTAMP_PATTERN)
        interfaces.library.profiling_assert_field("end", content_pattern=TIMESTAMP_PATTERN)

    def test_native_library(self):
        """ Language is set to native (though this is relevant only for ddprof)"""
        interfaces.library.profiling_assert_field("language:native")


@bug(library="cpp", reason="Need to understand how to activate profiling")
@bug(library="dotnet", reason="Need to understand how to activate profiling")
@bug(library="golang", reason="Need to understand how to activate profiling")
@bug(library="java", reason="Need to understand how to activate profiling")
@bug(library="php", reason="Need to understand how to activate profiling")
@bug(library="python", reason="Need to understand how to activate profiling")
@bug(library="ruby", reason="Need to understand how to activate profiling")
@scenario("PROFILING")
class Test_Basic:
    """ Basic testing of profiling """

    def test_library(self):
        """ All profiling libraries payload have recording-start and recording-end fields"""
        interfaces.library.profiling_assert_field("recording-start", content_pattern=TIMESTAMP_PATTERN)
        interfaces.library.profiling_assert_field("recording-end", content_pattern=TIMESTAMP_PATTERN)

    def test_agent(self):
        """ All profiling agent payload have recording-start and recording-end fields"""
        interfaces.agent.profiling_assert_field("recording-start", content_pattern=TIMESTAMP_PATTERN)
        interfaces.agent.profiling_assert_field("recording-end", content_pattern=TIMESTAMP_PATTERN)
