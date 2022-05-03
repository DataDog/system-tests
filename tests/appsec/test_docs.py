# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


import pytest
from utils import coverage, context, released


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(python="?")
@coverage.not_testable
class Test_InstallationInstructions:
    """ Detailed installation instructions """


@released(python="?")
@coverage.not_testable
class Test_InstallationDebugProcedure:
    """ Procedure to debug install """


@coverage.not_testable
class Test_PublicDocumentation:
    """ Public documentation is published """
