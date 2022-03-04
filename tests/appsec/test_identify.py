# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, released, bug, irrelevant, missing_feature, flaky, rfc
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@missing_feature(library="golang")
@missing_feature(library="dotnet")
@missing_feature(library="nodejs")
@missing_feature(library="java")
@missing_feature(library="php")
@missing_feature(library="python")
@missing_feature(library="ruby")
class Test_Basic(BaseTestCase):
    """ Basic tests for Identify SDK """

    def test_main(self):
        interfaces.library.append_not_implemented_validation()
