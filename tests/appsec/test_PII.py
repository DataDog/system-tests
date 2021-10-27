# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, released


@released(cpp="not relevant")
@released(golang="?" if context.weblog_variant != "echo-poc" else "not relevant: echo is not instrumented")
@released(dotnet="?", java="?", nodejs="?", php="?", python="?", ruby="?")
class Test_Scrubbing(BaseTestCase):
    def test_basic(self):
        raise NotImplementedError
