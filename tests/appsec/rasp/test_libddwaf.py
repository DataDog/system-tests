# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, scenarios
from tests.appsec.rasp.utils import find_series, validate_metric_tag_version


@features.rasp_local_file_inclusion
@features.rasp_sql_injection
@features.rasp_shell_injection
@features.rasp_server_side_request_forgery
@scenarios.appsec_rasp
class Test_Libddwaf_Version:
    """Test libddwaf version"""

    def test_min_version(self):
        """Checks data in waf.init metric to verify waf version"""
        min_version = [1, 20, 1]

        series = find_series(True, "appsec", "waf.init")
        assert series
        assert any(validate_metric_tag_version("waf_version", min_version, s) for s in series)
