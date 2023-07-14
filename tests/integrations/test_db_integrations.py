# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import weblog, interfaces, context, bug, missing_feature, scenarios
from utils.tools import logger
import pytest
import requests
from utils import context

integration_db_data = [
    {
        "service": "mysql",
        "db_type": "mysql",
        "db_instance": "world",
        "db_user": "mysqldb",
        "peer_hostname": "mysqldb",
        "db_password": "mysqldb",
        "request": {},
    },
    {
        "service": "postgresql",
        "db_type": "postgresql",
        "db_instance": "system_tests",
        "db_user": "system_tests_user",
        "peer_hostname": "postgres",
        "db_password": "system_tests",
        "request": {},
    },
    {
        "service": "sqlserver",
        "db_type": "sqlserver",
        "db_instance": "master",
        "db_user": "SA",
        "peer_hostname": "mssql",
        "db_password": "yourStrong(!)Password",
        "request": {},
    },
]


@pytest.fixture(params=integration_db_data, ids=[integration_db["service"] for integration_db in integration_db_data])
def integration_db(request):
    yield request.param


@missing_feature(
    condition=context.library != "java" and context.weblog_variant != "integrations-db",
    reason="Endpoint is not implemented on weblog",
)
@scenarios.integrations_db
class Test_Db_Integrations:
    """ Verify basic DB operations over different databases """

    # Weblog should support multiple datasources and the endpoint accepts parameters: service as DB identifier (mysql,postgre..) and 'operation' as db operation

    def setup_select(self, integration_db_id):
        integration_db = self._get_db_data(integration_db_id)
        integration_db["request"]["select"] = weblog.get(f"/db?service={integration_db_id}&operation=select")

    def test_select(self, integration_db):
        self._validate(integration_db, "select")

    def setup_select_error(self, integration_db_id):
        integration_db = self._get_db_data(integration_db_id)
        integration_db["request"]["select_error"] = weblog.get(
            f"/db?service={integration_db_id}&operation=select_error"
        )

    def test_select_error(self, integration_db):
        self._validate(integration_db, "select", request_id="select_error", db_exec_error=True)

    def setup_insert(self, integration_db_id):
        integration_db = self._get_db_data(integration_db_id)
        integration_db["request"]["insert"] = weblog.get(f"/db?service={integration_db_id}&operation=insert")

    def test_insert(self, integration_db):
        self._validate(integration_db, "insert")

    def setup_update(self, integration_db_id):
        integration_db = self._get_db_data(integration_db_id)
        integration_db["request"]["update"] = weblog.get(f"/db?service={integration_db_id}&operation=update")

    def test_update(self, integration_db):
        self._validate(integration_db, "update")

    def setup_delete(self, integration_db_id):
        integration_db = self._get_db_data(integration_db_id)
        integration_db["request"]["delete"] = weblog.get(f"/db?service={integration_db_id}&operation=delete")

    def test_delete(self, integration_db):
        self._validate(integration_db, "delete")

    def setup_procedure(self, integration_db_id):
        integration_db = self._get_db_data(integration_db_id)
        integration_db["request"]["call"] = weblog.get(f"/db?service={integration_db_id}&operation=procedure")

    def test_procedure(self, integration_db):
        self._validate(integration_db, "call")

    def _get_db_data(self, integration_db_id):
        return next(filter(lambda integration_db: integration_db["service"] == integration_db_id, integration_db_data))

    def _validate(self, integration_db, db_operation, request_id=None, db_exec_error=False):
        """ Search for the span for the current request, then search for sql child span and make the validations"""
        if not request_id:
            request_id = db_operation
        sql_found = False
        for data, trace, span in interfaces.library.get_spans(integration_db["request"][request_id]):
            for trace in data["request"]["content"]:
                for span_child in trace:
                    if (
                        span_child["parent_id"] == span["span_id"]
                        and span_child["type"] == "sql"
                        and span_child["trace_id"] == span["trace_id"]
                    ):
                        sql_found = True
                        assert integration_db["service"] == span_child["service"]
                        assert integration_db["db_type"] == span_child["meta"]["db.type"]
                        assert integration_db["db_instance"] == span_child["meta"]["db.instance"]
                        assert integration_db["db_user"] == span_child["meta"]["db.user"]
                        assert integration_db["peer_hostname"] == span_child["meta"]["peer.hostname"]
                        # Duration: Minimal validation, is a number and greater than 0
                        duration = span_child["duration"]
                        assert type(duration) == int and duration > 0
                        # Password no showed
                        for key in span_child["meta"]:
                            if key not in [
                                "peer.hostname",
                                "db.user",
                                "env",
                                "db.instance",
                            ]:  # These fields hostname, user and password are the same
                                assert span_child["meta"][key] != integration_db["db_password"]
                        # Check operation type
                        assert span_child["meta"]["db.operation"] == db_operation
                        assert span_child["resource"].replace("{", "").startswith(db_operation)
                        # Check db operation error
                        assert span_child["error"] == 0 if not db_exec_error else 1
        assert sql_found == True
