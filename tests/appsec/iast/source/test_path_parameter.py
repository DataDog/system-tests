# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_path_parameter
class TestPathParameter(BaseSourceTest):
    """Verify that request path is tainted"""

    endpoint = "/iast/source/path_parameter/test/user"
    source_type = "http.request.path.parameter"
    source_names = ["table"]
    source_value = "user"
    requests_kwargs = [{"method": "GET"}]
