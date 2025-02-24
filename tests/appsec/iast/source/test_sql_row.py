# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features
from tests.appsec.iast.utils import BaseSourceTest


@features.iast_source_sql
class TestSqlRow(BaseSourceTest):
    """Verify that database source is tainted"""

    endpoint = "/iast/source/sql/test"
    source_type = "sql.row.value"
    source_names = ["0.username", "USERNAME"]
    requests_kwargs = [{"method": "GET"}]
