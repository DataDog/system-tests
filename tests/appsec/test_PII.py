# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, released, interfaces
import pytest


if context.library == "cpp":
    pytestmark = pytest.mark.skip("not relevant")


@released(golang="?", dotnet="?", java="?", nodejs="?", php="?", python="0.57.3", ruby="?")
class Test_Scrubbing(BaseTestCase):
    """Appsec scrubs all sensitive data"""

    def test_basic(self):
        interfaces.library.append_not_implemented_validation()
