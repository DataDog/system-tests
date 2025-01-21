# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2025 Datadog, Inc.

from utils import rfc
import tests.debugger.utils as debugger

from utils import context, scenarios, features, bug, missing_feature

from utils.tools import logger


@rfc(
    "https://docs.google.com/document/d/1lhaEgBGIb9LATLsXxuKDesx4BCYixOcOzFnr4qTTemw/edit?pli=1&tab=t.0#heading=h.o5gstqo08gu5"
)
@features.debugger
@scenarios.debugger_code_origins
class Test_Debugger_Code_Origins(debugger._Base_Debugger_Test):
    ############ setup ############
    def _setup(self, request_path: str):
        self.initialize_weblog_remote_config()

        # Code origins will automatically be included in spans, so we don't
        # need to configure any probes.
        self.send_weblog_request(request_path)

    ############ test ############
    def setup_code_origin_present(self):
        self._setup("/healthcheck")

    @missing_feature(context.library == "cpp", reason="Not yet implemented")
    @missing_feature(context.library == "dotnet", reason="Not yet implemented")
    @missing_feature(context.library == "golang", reason="Not yet implemented")
    @missing_feature(context.library == "nodejs", reason="Not yet implemented")
    @missing_feature(
        context.library == "java",
        reason="Only spring-boot (without spring-mvc), gRPC, and micronaut are supported which aren't weblog variants",
    )
    @missing_feature(context.library == "php", reason="Not yet implemented")
    @missing_feature(context.library == "ruby", reason="Not yet implemented")
    def test_code_origin_present(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_all_weblog_responses_ok()

        code_origins_found = []
        for _, span in self.spans:
            resource = span.get("resource", None)
            logger.info(f"Resource: {resource}")
            # All web spans for the healthcheck should have code origins defined.
            if span.get("resource", None) == "GET /healthcheck" and span.get("type", None) == "web":
                code_origins_found.append(span["meta"]["_dd.code_origin.type"] != "")

        assert all(code_origins_found) and len(code_origins_found) > 0
