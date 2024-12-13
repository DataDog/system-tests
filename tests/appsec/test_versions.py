# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, interfaces, missing_feature, features


@features.appsec_miscs_internals
class Test_Events:
    """AppSec events uses events in span"""

    @missing_feature(context.library < "java@0.93.0")
    def test_appsec_in_traces(self):
        """AppSec sends event in traces"""

        for _ in interfaces.library.get_legacy_appsec_events():
            raise ValueError("You are using old AppSec communication")
