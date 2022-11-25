# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, missing_feature


@missing_feature(True, reason="Need to build endpoint on weblog")
class Test_Ssrf:
    """ Verify the /trace/ssrf endpoint is setup """

    def setup_main(self):
        self.r = weblog.get("/trace/ssrf")

    def test_main(self):
        interfaces.library.assert_trace_exists(self.r)
        interfaces.library.add_assertion(self.r.status_code == 200)
