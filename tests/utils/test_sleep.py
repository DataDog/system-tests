# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time
from utils import scenario


@scenario("SLEEP")
class Test_Sleep:
    def setup_sleep(self):
        """Sleep forever to allow you to perform some manual testing"""
        time.sleep(3600 * 24)

    def test_sleep(self):
        pass
