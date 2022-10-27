# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import BaseTestCase, interfaces, context, missing_feature, released


@released(cpp="?", golang="?", java="?", dotnet="?", nodejs="?", php="?", ruby="?")
@released(python="1.5.0rc2.dev")  # TODO : is it the good version number ?
@missing_feature(context.library == "python" and context.weblog_variant != "flask-poc", reason="Missing on weblog")
class Test_DistributedHttp(BaseTestCase):
    """ Verify behavior of http clients and distributed traces """

    def test_main(self):
        def validator():
            assert r.status_code == 200
            assert r.json() is not None
            data = r.json()
            assert "traceparent" in data["request_headers"]
            assert "x-datadog-parent-id" not in data["request_headers"]
            assert "x-datadog-sampling-priority" not in data["request_headers"]
            assert "x-datadog-tags" not in data["request_headers"]
            assert "x-datadog-trace-id" not in data["request_headers"]

            return True

        r = self.weblog_get("/make_distant_call", params={"url": "http://weblog:7777"})
        interfaces.library.assert_trace_exists(r)
        interfaces.library.add_final_validation(validator)
