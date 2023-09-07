# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, context, missing_feature, released, scenarios


@released(java="?", php="?", ruby="?")
@released(python="1.5.0rc2.dev")  # TODO : is it the good version number ?
@missing_feature(context.library == "python" and context.weblog_variant != "flask-poc", reason="Missing on weblog")
@scenarios.trace_propagation_style_w3c
class Test_DistributedHttp:
    """ Verify behavior of http clients and distributed traces """

    def setup_main(self):
        self.r = weblog.get("/make_distant_call", params={"url": "http://weblog:7777"})

    def test_main(self):

        interfaces.library.assert_trace_exists(self.r)

        assert self.r.status_code == 200
        assert self.r.json() is not None
        data = self.r.json()
        assert "traceparent" in data["request_headers"]
        assert "x-datadog-parent-id" not in data["request_headers"]
        assert "x-datadog-sampling-priority" not in data["request_headers"]
        assert "x-datadog-tags" not in data["request_headers"]
        assert "x-datadog-trace-id" not in data["request_headers"]
