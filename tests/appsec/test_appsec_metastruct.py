# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, context, interfaces, bug, missing_feature, scenarios, features


@features.security_events_metastruct
class Test_SecurityEvent_Metastruct:
    """Tests to verify that the meta struct appsec event feature is used by the tracer"""

    def setup_appsec_event_use_metastruct(self):
        self.r = weblog.get("/", headers={"User-Agent": "Arachni/v1"})

    def test_appsec_event_use_metastruct(self):
        spans = [s for _, s in interfaces.library.get_root_spans(request=self.r)]
        assert spans

        for span in spans:
            meta = span.get("meta", {})
            meta_struct = span.get("meta_struct", {})
            assert meta["appsec.event"] == "true"
            assert "_dd.appsec.json" not in meta
            assert "appsec" in meta_struct

            # The event is not null
            assert meta_struct.get("appsec", {}) not in [None, {}]

            # There is at least one rule triggered
            assert len(meta_struct["appsec"].get("triggers", [])) > 0

    def setup_iast_event_use_metastruct(self):
        # Using this vulnerability because that's one that is implemented in all tracers
        self.r = weblog.get("/iast/header_injection/test_insecure", data={"test": "dummyvalue"})

    def test_iast_event_use_metastruct(self):
        spans = [s for _, s in interfaces.library.get_root_spans(request=self.r)]
        assert spans

        for span in spans:
            meta = span.get("meta", {})
            meta_struct = span.get("meta_struct", {})
            assert meta["_dd.iast.enabled"] == "1"
            assert "_dd.iast.json" not in meta
            assert "iast" in meta_struct

            # The event is not null
            assert meta_struct.get("appsec", {}) not in [None, {}]

            # There is at least one vulnerability detected
            assert len(meta_struct["appsec"].get("vulnerabilities", [])) > 0
