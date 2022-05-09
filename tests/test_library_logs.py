# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, BaseTestCase, interfaces, irrelevant


class Test_NoExceptions(BaseTestCase):
    """There is not exception in dotnet-tracer-managed log files"""

    @irrelevant(context.library != "dotnet", reason="only for .NET")
    def test_dotnet(self):
        interfaces.library_dotnet_managed.assert_absence(
            pattern=r"[A-Za-z]+\.[A-Za-z]*Exception",
            allowed_patterns=[
                r"System.DllNotFoundException: Unable to load shared library 'Datadog.AutoInstrumentation.Profiler.Native.x64'"
            ],
        )
