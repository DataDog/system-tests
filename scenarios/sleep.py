# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import time


def test_sleep():
    """Sleep forever to allow you to perform some manual testing"""
    time.sleep(3600 * 24)
