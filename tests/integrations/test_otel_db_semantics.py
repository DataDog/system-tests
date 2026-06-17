# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

"""Validate that database (postgres) SQL spans honor the OpenTelemetry database semantic
conventions when ``DD_TRACE_OTEL_SEMANTICS_ENABLED=true`` (the OTEL_SEMANTICS_DB scenario).

This is the database counterpart to tests/test_otel_http_semantics.py. When the flag is on, SQL
spans should emit the OpenTelemetry DB attribute names instead of the Datadog ones (the Datadog
names are replaced, not added alongside).

NOTE: no tracer implements DB OTel semantics yet — the flag currently covers HTTP only — so these
tests are gated ``missing_feature`` everywhere. They encode the target contract and activate
per-tracer as database support lands.

Spec: https://opentelemetry.io/docs/specs/semconv/db/database-spans/
"""

from utils import context, features, scenarios

from .utils import BaseDbIntegrationsTestClass


@features.semantic_core_validations
@scenarios.otel_semantics_db
class Test_PostgresOtelSemantics(BaseDbIntegrationsTestClass):
    """Postgres SQL spans emit OpenTelemetry database semantic-convention attribute names."""

    db_service = "postgresql"

    def _setup_queries(self):
        # the inherited _setup issues the /db queries once (idempotent, shared across the class)
        self._setup()

    # one setup per test method, all aliased to the shared query setup (mirrors BaseDbIntegrationsTestClass)
    setup_db_system_name = _setup_queries
    setup_db_namespace = _setup_queries
    setup_db_operation_name = _setup_queries
    setup_db_query_text = _setup_queries
    setup_server_address = _setup_queries

    def _tracer_span_metas(self, excluded_operations: tuple[str, ...] = ("select_error",)):
        for db_operation, request in self.get_requests(excluded_operations=excluded_operations):
            yield db_operation, self.get_span_from_tracer(request).meta

    def test_db_system_name(self):
        """``db.type`` / ``db.system`` become ``db.system.name`` (the stable spec name) = postgresql."""
        for db_operation, meta in self._tracer_span_metas():
            assert meta.get("db.system.name") == "postgresql", f"failing for {db_operation}"
            assert "db.system" not in meta, "experimental db.system must be absent (stable name is db.system.name)"
            assert "db.type" not in meta, "legacy db.type must be absent in OTel mode"

    def test_db_namespace(self):
        """``db.name`` / ``db.instance`` become ``db.namespace`` (the database name)."""
        db_container = context.get_container_by_dd_integration_name(self.db_service)
        for db_operation, meta in self._tracer_span_metas():
            assert meta.get("db.namespace") == db_container.db_instance, f"failing for {db_operation}"
            assert "db.name" not in meta, "legacy db.name must be absent in OTel mode"
            assert "db.instance" not in meta, "legacy db.instance must be absent in OTel mode"

    def test_db_operation_name(self):
        """``db.operation`` becomes ``db.operation.name`` (the SQL operation, e.g. select/insert)."""
        for db_operation, meta in self._tracer_span_metas(excluded_operations=("select_error", "procedure")):
            assert db_operation in meta.get("db.operation.name", "").lower(), f"failing for {db_operation}"
            assert "db.operation" not in meta, "legacy db.operation must be absent in OTel mode"

    def test_db_query_text(self):
        """``db.statement`` becomes ``db.query.text``."""
        for db_operation, meta in self._tracer_span_metas(excluded_operations=("select_error", "procedure")):
            assert db_operation in meta.get("db.query.text", "").lower(), f"failing for {db_operation}"
            assert "db.statement" not in meta, "legacy db.statement must be absent in OTel mode"

    def test_server_address(self):
        """``out.host`` becomes ``server.address``."""
        for db_operation, meta in self._tracer_span_metas():
            assert meta.get("server.address"), f"server.address expected, failing for {db_operation}"
            assert "out.host" not in meta, "legacy out.host must be absent in OTel mode"
