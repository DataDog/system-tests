# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import tests.debugger.utils as debugger
from utils import scenarios, features, missing_feature, context, rfc, logger


@features.debugger_code_origins
@scenarios.debugger_probes_snapshot
class Test_Debugger_Code_Origins(debugger.BaseDebuggerTest):
    ############ test ############
    @rfc(
        "https://docs.google.com/document/d/1lhaEgBGIb9LATLsXxuKDesx4BCYixOcOzFnr4qTTemw/edit?pli=1&tab=t.0#heading=h.o5gstqo08gu5"
    )
    def setup_code_origin_entry_present(self):
        # Code origins are automatically included in spans, so we don't need to configure probes.
        self.initialize_weblog_remote_config()
        self.send_weblog_request("/healthcheck")

    @missing_feature(context.library == "dotnet", reason="Not yet implemented", force_skip=True)
    @missing_feature(
        context.library == "java" and context.weblog_variant != "spring-boot",
        reason="Implemented for spring-mvc",
        force_skip=True,
    )
    @missing_feature(context.library == "nodejs", reason="Not yet implemented for express", force_skip=True)
    @missing_feature(context.library == "ruby", reason="Not yet implemented", force_skip=True)
    def test_code_origin_entry_present(self):
        self.collect()

        self.assert_setup_ok()
        self.assert_all_weblog_responses_ok()

        code_origins_entry_found = False
        for span in self.all_spans:
            # Web spans for the healthcheck should have code origins defined.
            resource, resource_type = span.get("resource", None), span.get("type", None)
            logger.debug(span)

            if resource == "GET /healthcheck" and resource_type == "web":
                code_origin_type = span["meta"].get("_dd.code_origin.type", "")
                code_origins_entry_found = code_origin_type == "entry"

        assert code_origins_entry_found
