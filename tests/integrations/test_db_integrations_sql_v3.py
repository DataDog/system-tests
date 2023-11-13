# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import functools
import inspect

from utils import context, bug, missing_feature, irrelevant, scenarios, flaky
from utils.tools import logger

import pytest
from utils import weblog, interfaces
from .sql_utils import BaseDbIntegrationsTestClass

# Define the data for test case generation
test_sql_operations = ["select", "insert", "update", "delete", "procedure", "select_error"]
test_sql_services = ["mysql", "postgres", "mssql"]


def pytest_generate_tests(metafunc):
    """ Generate parametrized tests for given sql_operations (basic sql operations; ie select,insert...) over sql_services (db services ie mysql,mssql...)"""
    if (
        "test_sql_service"
        and "test_sql_operation" in metafunc.fixturenames
        and context.scenario == scenarios.integrations_v3
    ):
        test_parameters = []
        test_ids = []
        for test_sql_service in test_sql_services:
            logger.info("Initializing DB...")
            weblog.get("/db", params={"service": test_sql_service, "operation": "init"}, timeout=20)
            for test_sql_operation in test_sql_operations:
                weblog_request = weblog.get(
                    "/db", params={"service": test_sql_service, "operation": test_sql_operation}
                )
                test_parameters.append((test_sql_service, test_sql_operation, weblog_request))
                test_ids.append("srv:" + test_sql_service + ",op:" + test_sql_operation)
        metafunc.parametrize("test_sql_service,test_sql_operation,weblog_request", test_parameters, ids=test_ids)


sql_parametrized_nodes = {}


def missing_sql_feature(func=None, condition=None, library=None, reason=None):
    if func is None:
        return functools.partial(missing_sql_feature, condition=condition, library=library, reason=reason)

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        return eval_codition(func, condition, "missing_feature", library, reason, *args, **kwargs)

    return decorator


def sql_irrelevant(func=None, condition=None, library=None, reason=None):
    if func is None:
        return functools.partial(sql_irrelevant, condition=condition, library=library, reason=reason)

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        return eval_codition(func, condition, "irrelevant", library, reason, *args, **kwargs)

    return decorator


def sql_bug(func=None, condition=None, library=None, reason=None):
    if func is None:
        return functools.partial(sql_bug, condition=condition, library=library, reason=reason)

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        return eval_codition(func, condition, "bug", library, reason, *args, **kwargs)

    return decorator


def eval_codition(func, condition, condition_type, library, reason, *args, **kwargs):
    """We allway evaluate the condition in same way, but if condition evaluation is true, we mark the tests as xfail or skip"""
    # Library evaluation
    eval_library = True
    if library is not None and context.library != library:
        eval_library = False
    # Condition evaluation
    eval_condition = True
    if condition is not None:
        codition_param_values = {}
        for param_name in inspect.signature(condition).parameters:
            codition_param_values[param_name] = kwargs.get(param_name)
        eval_condition = False if not condition(**codition_param_values) else True

    # Full evaluation and set skip/xpass if needed
    if eval_library and eval_condition:
        full_reason = f"{condition_type}:" if reason is None else f"{condition_type}: {reason}"
        if "irrelevant" == condition_type:
            pytest.skip(full_reason)
        else:
            sql_parametrized_nodes[hex(id(args[0]))].add_marker(pytest.mark.xfail(reason=full_reason))

    return func(*args, **kwargs)


@pytest.fixture
def manage_sql_decorators(request):
    """ This fixture add to global map all marked nodes, in order to add pytests marks from decorator"""
    sql_parametrized_nodes[hex(id(request.function.__self__))] = request.node


@scenarios.integrations_v3
class Test_One:
    @missing_sql_feature(condition=lambda test_sql_operation: test_sql_operation == "insert", reason="ESTO Y AQUELLO")
    @missing_sql_feature(
        library="nodejs", condition=lambda test_sql_operation: test_sql_operation == "select", reason="ESTO Y AQUELLO"
    )
    #  @missing_feature(library="nodejs", reason="OTRAOTRA")
    @pytest.mark.usefixtures("manage_sql_decorators")  # Mandatory for decorators to work :-(
    def test_addition(self, test_sql_service, test_sql_operation, weblog_request):
        logger.debug(f"Parametrizedd for operation::{test_sql_operation} and service: {test_sql_service}")
        assert True

    @irrelevant(library="nodejs", reason="TRUKUTRUKU")
    def test_addition2(self):
        logger.debug("Parametrizedd!!")
        assert True
