# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, context, interfaces, bug, missing_feature, scenarios, features

@features.security_events_metastruct
class Test_SecurityEvent_Metastruct:
    """Tests to verify that the meta struct appsec event feature is used by the tracer"""

    def setup_security_event_use_metastruct(self):
        self.r = weblog.get("/", headers={"User-Agent": "Arachni/v1"})

    def test_security_event_use_metastruct(self, test_agent):
        assert test_agent.info()["span_meta_structs"] == True

        for _, span in interfaces.library.get_root_spans(request=self.r):
            meta = span.get("meta", {})
            meta_struct = span.get("meta_struct", {})
            assert meta["appsec.event"] == "true"
            assert "_dd.appsec.json" not in meta
            assert "appsec" in meta_struct

            # The event is not null
            assert meta_struct.get("appsec", {}) not in [None, {}]

            # There is at least one rule triggered
            assert len(meta_struct["appsec"].get("triggers", [])) > 0