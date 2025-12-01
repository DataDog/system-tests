# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_uri
class TestURI(BaseSourceTest):
    """Verify that URL is tainted"""

    endpoint = "/iast/source/uri/test"
    requests_kwargs = [{"method": "GET"}]
    source_type = "http.request.uri"
    source_value = "http://localhost:7777/iast/source/uri/test"
    source_names = None
