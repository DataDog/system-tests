# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from utils import context, released, coverage


@released(java="?", php="?", python="?", ruby="?")
@coverage.not_implemented
class Test_Scrubbing:
    """Appsec scrubs all sensitive data"""
