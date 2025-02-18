# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_multipart
class TestMultipart(BaseSourceTest):
    """Verify that multipart parameter is tainted"""

    endpoint = "/iast/source/multipart/test"
    requests_kwargs = [{"method": "POST", "files": {"file1": ("file1", "bsldhkuqwgervf")}}]
    source_type = "http.request.multipart.parameter"
    source_names = ["name", "Content-Disposition"]
    source_value = None
