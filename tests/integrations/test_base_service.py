# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import context, weblog, interfaces, scenarios, features, irrelevant


@features.base_service
@scenarios.integrations
class Test_BaseService_RootSpan:
    """Verify that the root/entry span never carries _dd.base_service.

    _dd.base_service is only added when a span's service name differs from the
    global service (DD_SERVICE).  The root web span's service IS the global
    service, so the tag must be absent.
    """

    def setup_root_span_has_no_base_service(self):
        self.req = weblog.get("/")

    def test_root_span_has_no_base_service(self):
        found_root = False
        for _, _, span in interfaces.library.get_spans(request=self.req, full_trace=True):
            if span.get("parent_id") in (0, None):
                found_root = True
                assert "_dd.base_service" not in span.get("meta", {}), (
                    f"Root span should not have _dd.base_service, but got: {span['meta'].get('_dd.base_service')!r}"
                )
        assert found_root, "No root span found in trace"


@features.base_service
@scenarios.integrations
@irrelevant(context.weblog_variant == "spring-boot-3-native", reason="/rasp/sqli endpoint is not available")
class Test_BaseService_SqlSpan:
    """Verify that SQL spans carry _dd.base_service when the integration overrides the service name.

    Database integrations typically set span.service to the DB engine name
    (e.g. 'postgresql', 'mysql').  Any such span must have _dd.base_service
    set to the root service so Datadog can attribute the operation back to the
    originating application.
    """

    def setup_sql_span_has_base_service(self):
        self.req = weblog.get("/rasp/sqli", params={"user_id": "1"})

    def test_sql_span_has_base_service(self):
        root_service = None
        sql_spans_with_different_service = []

        for _, _, span in interfaces.library.get_spans(request=self.req, full_trace=True):
            if span.get("parent_id") in (0, None):
                root_service = span.get("service")

        assert root_service is not None, "Could not determine root service from trace"

        for _, _, span in interfaces.library.get_spans(request=self.req, full_trace=True):
            if span.get("type") == "sql" and span.get("service") != root_service:
                sql_spans_with_different_service.append(span)

        assert sql_spans_with_different_service, (
            f"Expected at least one SQL span with service != '{root_service}'. "
            "Check that the weblog generates database spans with an integration-specific service name."
        )

        for span in sql_spans_with_different_service:
            service = span.get("service")
            meta = span.get("meta", {})
            assert "_dd.base_service" in meta, (
                f"SQL span with service='{service}' (differs from root='{root_service}') "
                f"must have _dd.base_service set, but it is missing"
            )
            assert meta["_dd.base_service"] == root_service, (
                f"_dd.base_service should be '{root_service}', got: {meta['_dd.base_service']!r}"
            )
