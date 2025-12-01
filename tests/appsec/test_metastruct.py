# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, rfc, scenarios, features


@rfc("https://docs.google.com/document/d/1iWQsOfT6Lg_IFyvQeqry9wVmXOE2Yav0X4MgOTk7mks")
@features.security_events_metastruct
class Test_SecurityEvents_Appsec_Metastruct_Enabled:
    """Test to verify that appsec events are correctly set in meta struct when supported by the agent."""

    def setup_appsec_event_use_metastruct(self):
        self.r = weblog.get("/", headers={"User-Agent": "Arachni/v1"})

    def test_appsec_event_use_metastruct(self):
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        meta_struct = span.get("meta_struct", {})
        assert meta["appsec.event"] == "true"
        assert "_dd.appsec.json" not in meta
        assert "appsec" in meta_struct

        # The event is not null
        assert meta_struct.get("appsec", {}) not in [None, {}]

        # There is at least one rule triggered
        assert len(meta_struct["appsec"].get("triggers", [])) > 0


@features.security_events_metastruct
class Test_SecurityEvents_Iast_Metastruct_Enabled:
    """Test to verify that IAST events are correctly set in meta struct when supported by the agent."""

    def setup_iast_event_use_metastruct(self):
        # Triggers a vulnerability
        self.r = weblog.get("/iast/source/cookievalue/test", cookies={"table": "user"})

    def test_iast_event_use_metastruct(self):
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        metrics = span.get("metrics", {})
        meta_struct = span.get("meta_struct", {})
        assert meta.get("_dd.iast.enabled") == "1" or metrics.get("_dd.iast.enabled") == 1.0
        assert "_dd.iast.json" not in meta
        assert "iast" in meta_struct

        # The event is not null
        assert meta_struct.get("iast", {}) not in [None, {}]

        # There is at least one vulnerability detected
        assert len(meta_struct["iast"].get("vulnerabilities", [])) > 0


@features.security_events_metastruct
@scenarios.appsec_meta_struct_disabled
class Test_SecurityEvents_Appsec_Metastruct_Disabled:
    """Fallback: Test to verify that Appsec events are set in the json tag when meta struct is not supported by the agent."""

    def setup_appsec_event_fallback_json(self):
        self.r = weblog.get("/", headers={"User-Agent": "Arachni/v1"})

    def test_appsec_event_fallback_json(self):
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        meta_struct = span.get("meta_struct", {})
        assert meta["appsec.event"] == "true"
        assert "_dd.appsec.json" in meta
        assert "appsec" not in meta_struct

        # The event is not null
        assert meta.get("_dd.appsec.json", {}) not in [None, {}]

        # There is at least one rule triggered
        assert len(meta["_dd.appsec.json"].get("triggers", [])) > 0


@features.security_events_metastruct
@scenarios.appsec_meta_struct_disabled
class Test_SecurityEvents_Iast_Metastruct_Disabled:
    """Fallback: Test to verify that IAST events are set in the json tag when meta struct is not supported by the agent."""

    def setup_iast_event_fallback_json(self):
        # Triggers a vulnerability
        self.r = weblog.get("/set_cookie", params={"name": "metastruct-no", "value": "no"})

    def test_iast_event_fallback_json(self):
        span = interfaces.library.get_root_span(request=self.r)
        meta = span.get("meta", {})
        meta_struct = span.get("meta_struct", {})
        assert meta["_dd.iast.enabled"] == "1"
        assert "_dd.iast.json" in meta
        assert "iast" not in meta_struct

        # The event is not null
        assert meta.get("_dd.iast.json", {}) not in [None, {}]

        # There is at least one vulnerability detected
        assert len(meta["_dd.iast.json"].get("vulnerabilities", [])) > 0
