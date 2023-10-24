# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage
from .._test_iast_fixtures import BaseSourceTest


@coverage.basic
class TestPath(BaseSourceTest):
    """Verify that request path is tainted"""

    endpoint = "/iast/source/path/test"
    source_type = "http.request.path"
    source_name = None
    source_value = "/iast/source/path/test"
    requests_kwargs = [{"method": "GET"}]
