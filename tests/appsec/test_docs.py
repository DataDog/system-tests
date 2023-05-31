# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


import pytest
from utils import coverage, context, released, missing_feature


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(python="1.4.2")
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
@coverage.not_testable
class Test_InstallationInstructions:
    """Detailed installation instructions"""


@released(python="1.4.2")
@coverage.not_testable
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
class Test_InstallationDebugProcedure:
    """Procedure to debug install"""


@released(python="1.4.2")
@coverage.not_testable
@missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
class Test_PublicDocumentation:
    """Public documentation is published"""
